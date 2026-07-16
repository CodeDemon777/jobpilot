"""JobPilot CLI — entry point for all commands."""

import asyncio
import io
import os
import sys
from typing import Optional

# Force UTF-8 output on Windows to avoid cp1252 encoding errors
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from jobpilot.config import MATCH_THRESHOLD, DEFAULT_PORT
from jobpilot.models import JobListing, Application
from jobpilot import database as db
from jobpilot.profile import load_profile, save_profile, update_profile
from jobpilot.matcher import compute_match
from jobpilot.scraper import SCRAPERS

app = typer.Typer(
    name="jobpilot",
    help="JobPilot - AI-powered job scraping and matching system",
    no_args_is_help=True,
)
console = Console(force_terminal=True)

# --- Scan Command ---

@app.command()
def scan(
    source: str = typer.Option("all", help="Scraper source: greenhouse, remoteok, or all"),
    role: str = typer.Option("", help="Job title or role to search for"),
    location: str = typer.Option("", help="Location filter"),
    limit: int = typer.Option(50, help="Max jobs to return per source"),
):
    """Scan job boards for new opportunities."""
    console.print(Panel(f"[bold blue]Scanning jobs: source={source}, role={role}, location={location}[/]", title="JobPilot Scan"))

    async def _run():
        all_jobs = []
        scrapers_to_run = SCRAPERS if source == "all" else {source: SCRAPERS[source]}

        for name, scraper_cls in scrapers_to_run.items():
            console.print(f"  [dim]Searching {name}...[/]")
            try:
                scraper = scraper_cls()
                jobs = await scraper.search(query=role, location=location)
                jobs = jobs[:limit]
                all_jobs.extend(jobs)
                console.print(f"  [green][OK] {name}: {len(jobs)} jobs found[/]")
            except Exception as e:
                console.print(f"  [red][FAIL] {name}: {e}[/]")

        # Store in database
        new_count = 0
        for job in all_jobs:
            is_new = db.upsert_job(job)
            if is_new:
                new_count += 1
                # Auto-upsert company
                company = db.Company(name=job.company, career_page=job.url.rsplit("/", 1)[0])
                db.upsert_company(company)

        console.print(f"\n[bold green]Scan complete: {len(all_jobs)} jobs found, {new_count} new[/]")
        return all_jobs

    asyncio.run(_run())


# --- Match Command ---

@app.command()
def match(
    min_score: float = typer.Option(MATCH_THRESHOLD, help="Minimum match score (0-1)"),
    limit: int = typer.Option(20, help="Max results to show"),
    run_scan: bool = typer.Option(False, "--scan", help="Run a scan before matching"),
):
    """Match jobs against your profile and rank by score."""
    profile = load_profile()

    if not profile.name:
        console.print("[yellow]No profile found. Run 'jobpilot profile edit' first.[/]")
        return

    if run_scan:
        console.print("[dim]Running scan first...[/]")
        # This would call scan, but for simplicity we skip inline

    jobs = db.get_all_jobs()
    if not jobs:
        console.print("[yellow]No jobs found. Run 'jobpilot scan' first.[/]")
        return

    console.print(f"[dim]Matching {len(jobs)} jobs against your profile...[/]")

    results = []
    for job in jobs:
        result = compute_match(profile, job)
        if result.overall_score >= min_score:
            db.save_match_result(result)
            results.append((job, result))

    results.sort(key=lambda x: x[1].overall_score, reverse=True)
    results = results[:limit]

    # Display results
    table = Table(title="Top Matches", box=box.ROUNDED, show_lines=True)
    table.add_column("Score", style="bold", width=7)
    table.add_column("Company", style="cyan")
    table.add_column("Role", style="white")
    table.add_column("Location", style="dim")
    table.add_column("Skills", style="green")

    for job, result in results:
        score_pct = f"{result.overall_score:.0%}"
        if result.overall_score >= 0.8:
            score_style = f"[bold green]{score_pct}[/]"
        elif result.overall_score >= 0.6:
            score_style = f"[yellow]{score_pct}[/]"
        else:
            score_style = f"[dim]{score_pct}[/]"

        skills_str = ", ".join(result.missing_skills[:3]) if result.missing_skills else "all matched"
        table.add_row(score_style, job.company, job.title, job.location, skills_str)

    console.print(table)
    console.print(f"\n[dim]Showing {len(results)} jobs with score ≥ {min_score:.0%}[/]")


# --- Track Command ---

track_app = typer.Typer(help="Track job applications")
app.add_typer(track_app, name="track")


@track_app.command("list")
def track_list(
    status: str = typer.Option("", help="Filter by status: discovered, applied, interview, etc."),
):
    """List tracked applications."""
    apps = db.get_applications(status=status)

    if not apps:
        console.print("[yellow]No applications tracked yet.[/]")
        return

    table = Table(title="Applications", box=box.ROUNDED)
    table.add_column("Company", style="cyan")
    table.add_column("Role", style="white")
    table.add_column("Status", style="bold")
    table.add_column("Score", style="green")
    table.add_column("Updated", style="dim")

    status_colors = {
        "discovered": "dim", "applied": "blue", "assessment": "yellow",
        "interview": "green", "offer": "bold green", "rejected": "red",
    }

    for app_item in apps:
        color = status_colors.get(app_item.status, "white")
        score = f"{app_item.match_score:.0%}" if app_item.match_score else "-"
        table.add_row(
            app_item.company,
            app_item.role,
            f"[{color}]{app_item.status}[/]",
            score,
            app_item.updated_date[:10] if app_item.updated_date else "-",
        )

    console.print(table)


@track_app.command("add")
def track_add(
    job_id: str = typer.Argument(help="Job ID to track"),
    status: str = typer.Option("discovered", help="Initial status"),
    notes: str = typer.Option("", help="Notes about this application"),
):
    """Add a job to your application tracker."""
    job = db.get_job(job_id)
    if not job:
        console.print(f"[red]Job not found: {job_id}[/]")
        return

    profile = load_profile()
    match_result = compute_match(profile, job)

    app_item = Application(
        job_id=job.id,
        company=job.company,
        role=job.title,
        status=status,
        match_score=match_result.overall_score,
        notes=notes,
    )
    db.upsert_application(app_item)
    console.print(f"[green][OK] Tracking: {job.company} - {job.title} ({match_result.overall_score:.0%} match)[/]")


@track_app.command("update")
def track_update(
    app_id: str = typer.Argument(help="Application ID"),
    status: str = typer.Option(..., help="New status"),
    notes: str = typer.Option("", help="Additional notes"),
):
    """Update an application's status."""
    found = db.update_application_status(app_id, status)
    if found:
        console.print(f"[green][OK] Updated to '{status}'[/]")
    else:
        console.print(f"[red]Application not found: {app_id}[/]")


# --- Profile Command ---

profile_app = typer.Typer(help="Manage your user profile")
app.add_typer(profile_app, name="profile")


@profile_app.command("show")
def profile_show():
    """Display your current profile."""
    profile = load_profile()
    if not profile.name:
        console.print("[yellow]No profile configured. Run 'jobpilot profile edit'.[/]")
        return

    panel_content = f"""[bold]{profile.name}[/]
Email: {profile.email}
Phone: {profile.phone}
Location: {profile.location}, {profile.country}
LinkedIn: {profile.linkedin}
GitHub: {profile.github}
Experience: {profile.experience_years} years
Remote: {profile.remote_preference}
Salary: {profile.expected_salary}

[bold]Skills:[/]
{', '.join(profile.skills) or '(none)'}

[bold]Languages:[/]
{', '.join(profile.programming_languages) or '(none)'}

[bold]Frameworks:[/]
{', '.join(profile.frameworks) or '(none)'}

[bold]Cloud:[/]
{', '.join(profile.cloud_platforms) or '(none)'}

[bold]Preferred Roles:[/]
{', '.join(profile.preferred_roles) or '(none)'}

[bold]Preferred Locations:[/]
{', '.join(profile.preferred_locations) or '(none)'}
"""
    console.print(Panel(panel_content.strip(), title="Your Profile", border_style="blue"))


@profile_app.command("edit")
def profile_edit():
    """Open profile YAML in default editor."""
    from jobpilot.config import PROFILE_PATH
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    console.print(f"[dim]Edit your profile at: {PROFILE_PATH}[/]")
    console.print("[dim]Then run 'jobpilot profile show' to verify.[/]")


# --- Companies Command ---

@app.command("companies")
def companies_list():
    """List all tracked companies."""
    companies = db.get_companies()
    if not companies:
        console.print("[yellow]No companies tracked yet.[/]")
        return

    table = Table(title="Companies", box=box.ROUNDED)
    table.add_column("Company", style="cyan")
    table.add_column("Industry", style="white")
    table.add_column("Jobs", style="green")
    table.add_column("Career Page", style="dim")

    for c in companies:
        table.add_row(c.name, c.industry or "-", str(c.job_count), c.career_page or "-")

    console.print(table)


# --- Report Command ---

@app.command()
def report():
    """Show overall statistics."""
    stats = db.get_stats()
    profile = load_profile()

    panel_content = f"""[bold]Total Jobs Scanned:[/] {stats['total_jobs']}
[bold]Companies Tracked:[/] {stats['total_companies']}
[bold]Applications:[/] {stats['total_applications']}
[bold]Average Match Score:[/] {stats['average_match_score']:.0%}

[bold]Jobs by Source:[/]"""

    for source in stats["top_sources"]:
        panel_content += f"\n  {source['source']}: {source['count']}"

    console.print(Panel(panel_content.strip(), title="JobPilot Report", border_style="blue"))


# --- Seed Command ---

@app.command()
def seed():
    """Seed database with sample jobs and profile for testing."""
    from jobpilot.models import JobListing, UserProfile

    profile = UserProfile(
        name="Tivya",
        email="tivya@example.com",
        location="remote",
        country="global",
        skills=["python", "javascript", "react", "fastapi", "docker", "aws", "postgresql", "git"],
        programming_languages=["python", "javascript", "typescript", "go"],
        frameworks=["fastapi", "react", "django", "node.js"],
        cloud_platforms=["aws", "docker", "kubernetes"],
        experience_years=4,
        education=[{"degree": "B.S. Computer Science", "school": "University"}],
        preferred_roles=["software engineer", "backend developer", "full stack"],
        preferred_locations=["remote"],
        remote_preference="remote",
    )
    save_profile(profile)
    print("[OK] Profile saved to data/profile.yaml")

    sample_jobs = [
        JobListing(company="Stripe", title="Software Engineer, Payments", location="Remote", remote_status="remote",
                   required_skills=["python", "ruby", "postgresql"], preferred_skills=["aws", "docker"],
                   experience_years=3, description="Build payment infrastructure. Python/Ruby, PostgreSQL, AWS.",
                   url="https://stripe.com/jobs/example1", source="greenhouse"),
        JobListing(company="Vercel", title="Senior Frontend Engineer", location="Remote", remote_status="remote",
                   required_skills=["react", "typescript", "next.js"], preferred_skills=["node.js", "vercel"],
                   experience_years=5, description="Build the future of web deployment. React, TypeScript, Next.js.",
                   url="https://vercel.com/jobs/example2", source="greenhouse"),
        JobListing(company="Discord", title="Backend Engineer, Infrastructure", location="San Francisco, CA",
                   remote_status="hybrid", required_skills=["python", "rust", "postgresql"], preferred_skills=["kubernetes"],
                   experience_years=4, description="Scale Discord infrastructure. Python, Rust, PostgreSQL, K8s.",
                   url="https://discord.com/careers/example3", source="greenhouse"),
        JobListing(company="GitLab", title="Full Stack Developer", location="Remote", remote_status="remote",
                   required_skills=["ruby", "javascript", "postgresql"], preferred_skills=["git", "docker"],
                   experience_years=3, description="Contribute to GitLab. Ruby on Rails, JavaScript, PostgreSQL.",
                   url="https://gitlab.com/jobs/example4", source="greenhouse"),
        JobListing(company="Figma", title="Software Engineer, Design Tools", location="Remote", remote_status="remote",
                   required_skills=["typescript", "webgl", "react"], preferred_skills=["c++", "wasm"],
                   experience_years=4, description="Build collaborative design tools. TypeScript, WebGL, React.",
                   url="https://figma.com/careers/example5", source="greenhouse"),
        JobListing(company="RemoteOK", title="Python Developer, API", location="Remote", remote_status="remote",
                   required_skills=["python", "fastapi", "postgresql"], preferred_skills=["redis", "docker"],
                   experience_years=2, description="Build API services. Python, FastAPI, PostgreSQL, Redis.",
                   url="https://remoteok.com/jobs/example6", source="remoteok"),
        JobListing(company="Notion", title="Software Engineer, Core", location="Remote", remote_status="remote",
                   required_skills=["typescript", "react", "node.js"], preferred_skills=["postgresql", "redis"],
                   experience_years=3, description="Build Notion's core product. TypeScript, React, Node.js.",
                   url="https://notion.so/careers/example7", source="greenhouse"),
        JobListing(company="Ramp", title="Backend Engineer", location="New York, NY", remote_status="hybrid",
                   required_skills=["python", "django", "postgresql"], preferred_skills=["aws", "terraform"],
                   experience_years=3, description="Build finance tools. Python, Django, PostgreSQL, AWS.",
                   url="https://ramp.com/careers/example8", source="greenhouse"),
        JobListing(company="Cloudflare", title="Systems Engineer, Workers", location="Austin, TX",
                   remote_status="hybrid", required_skills=["rust", "javascript", "go"], preferred_skills=["linux", "networking"],
                   experience_years=5, description="Build Cloudflare Workers runtime. Rust, JS, Go.",
                   url="https://cloudflare.com/careers/example9", source="greenhouse"),
        JobListing(company="Scale AI", title="ML Engineer, Data Platform", location="San Francisco, CA",
                   remote_status="hybrid", required_skills=["python", "pytorch", "spark"], preferred_skills=["kubernetes", "aws"],
                   experience_years=4, description="Build ML data platform. Python, PyTorch, Spark.",
                   url="https://scale.com/careers/example10", source="greenhouse"),
    ]

    new_count = 0
    for job in sample_jobs:
        is_new = db.upsert_job(job)
        if is_new:
            new_count += 1
            db.upsert_company(db.Company(name=job.company))

    print(f"[OK] Seeded {len(sample_jobs)} sample jobs ({new_count} new)")
    print("Run 'jobpilot match' to see match scores against your profile.")


# --- Serve Command ---

@app.command()
def serve(
    port: int = typer.Option(DEFAULT_PORT, help="Port for web dashboard"),
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
):
    """Start the web dashboard."""
    console.print(Panel(f"[bold green]Starting JobPilot dashboard at http://{host}:{port}[/]", title="JobPilot Web"))
    import uvicorn
    uvicorn.run("jobpilot.web.app:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    app()
