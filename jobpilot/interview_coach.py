"""Interview Preparation Assistant for JobPilot."""

import random
from jobpilot.resume_analyzer import _extract_skills, _extract_contact

# Question templates by category and difficulty
QUESTION_BANK = {
    "technical": {
        "beginner": [
            {
                "q": "What is {skill} and how have you used it?",
                "a": "{skill} is a technology I've worked with extensively. In my projects, I've used it to build scalable applications, handling everything from data processing to user interface development.",
                "tips": "Be specific about your usage. Mention a concrete project or task.",
            },
            {
                "q": "Can you explain the difference between {skill} and {skill2}?",
                "a": "While both serve similar purposes, they have different strengths. {skill} is known for its flexibility and ecosystem, while {skill2} excels in performance and type safety. I've chosen between them based on project requirements.",
                "tips": "Show understanding of trade-offs. Give examples of when you'd use each.",
            },
            {
                "q": "How do you approach debugging in {skill}?",
                "a": "I follow a systematic approach: reproduce the issue, check logs and error messages, isolate the problem area, use debugging tools, and verify the fix. I've found that logging and unit tests help prevent many issues.",
                "tips": "Demonstrate methodical thinking. Mention specific tools you use.",
            },
            {
                "q": "What are the key principles of {skill}?",
                "a": "Key principles include modularity, separation of concerns, and reusability. I apply these principles in my work by writing clean, well-organized code that's easy to maintain and extend.",
                "tips": "Connect principles to your actual work experience.",
            },
        ],
        "intermediate": [
            {
                "q": "Describe a challenging {skill} project you worked on.",
                "a": "I worked on a project that required scaling our application to handle 10x traffic. I implemented caching strategies, optimized database queries, and introduced load balancing. The result was a 60% improvement in response times.",
                "tips": "Use the STAR method. Quantify your impact.",
            },
            {
                "q": "How would you design a system using {skill}?",
                "a": "I'd start by defining requirements, then design the architecture with scalability in mind. Key components would include a load balancer, application layer, data storage, and caching. I'd use {skill} for its strengths in this area.",
                "tips": "Show architectural thinking. Consider scalability and maintainability.",
            },
            {
                "q": "What are common pitfalls when working with {skill}?",
                "a": "Common pitfalls include not handling edge cases, poor error handling, and not considering performance implications. I've learned to write comprehensive tests, implement proper error handling, and profile performance regularly.",
                "tips": "Demonstrate experience with real-world challenges.",
            },
            {
                "q": "How do you ensure code quality in {skill} projects?",
                "a": "I use a combination of code reviews, automated testing, linting, and CI/CD pipelines. I also practice refactoring regularly and follow established design patterns to maintain clean, maintainable code.",
                "tips": "Show commitment to quality and teamwork.",
            },
        ],
        "advanced": [
            {
                "q": "How would you optimize a {skill} application for performance?",
                "a": "I'd profile to identify bottlenecks, then optimize at multiple levels: algorithm improvements, caching strategies, database query optimization, and resource management. I'd also consider architectural changes like async processing or microservices.",
                "tips": "Demonstrate deep understanding of performance optimization.",
            },
            {
                "q": "Describe your approach to migrating a legacy system to {skill}.",
                "a": "I'd use a strangler fig pattern: gradually replacing components while maintaining the existing system. Start with the least risky components, ensure comprehensive testing, and have rollback plans. Communication with stakeholders is crucial.",
                "tips": "Show strategic thinking and risk management.",
            },
            {
                "q": "How would you handle a production incident involving {skill}?",
                "a": "First, I'd assess the impact and communicate with stakeholders. Then I'd identify the root cause, implement a fix or rollback, and ensure monitoring catches similar issues. Finally, I'd conduct a blameless post-mortem to prevent recurrence.",
                "tips": "Demonstrate calm under pressure and systematic problem-solving.",
            },
            {
                "q": "What architectural patterns would you use for a large-scale {skill} application?",
                "a": "I'd consider microservices for independent scaling, event-driven architecture for loose coupling, and CQRS for read/write optimization. The choice depends on team size, complexity, and scalability requirements.",
                "tips": "Show depth of architectural knowledge.",
            },
        ],
    },
    "behavioral": {
        "beginner": [
            {
                "q": "Tell me about yourself.",
                "a": "I'm a passionate developer with experience in building web applications. I enjoy solving complex problems and learning new technologies. I'm looking for an opportunity to grow while contributing to meaningful projects.",
                "tips": "Keep it concise. Focus on relevant experience and enthusiasm.",
            },
            {
                "q": "Why are you interested in this role?",
                "a": "This role aligns with my skills in {skills} and my interest in {industry}. I'm excited about the opportunity to work on challenging projects and contribute to the team's success.",
                "tips": "Research the company. Connect your skills to their needs.",
            },
            {
                "q": "What are your strengths?",
                "a": "My strengths include strong problem-solving abilities, attention to detail, and effective communication. I'm also a quick learner who adapts well to new technologies and team environments.",
                "tips": "Back up claims with examples.",
            },
            {
                "q": "What is your greatest weakness?",
                "a": "I sometimes spend too much time perfecting details. I've learned to balance this by setting clear deadlines and focusing on the most impactful aspects first, while still maintaining quality.",
                "tips": "Be honest but show self-awareness and improvement.",
            },
        ],
        "intermediate": [
            {
                "q": "Describe a time you had a conflict with a teammate.",
                "a": "I once disagreed with a colleague about implementation approach. I scheduled a meeting to understand their perspective, shared my concerns with data, and we found a compromise that combined the best of both approaches.",
                "tips": "Show emotional intelligence and conflict resolution skills.",
            },
            {
                "q": "Tell me about a project you're proud of.",
                "a": "I led the development of a real-time analytics dashboard that reduced decision-making time by 40%. I architected the backend, mentored junior developers, and delivered ahead of schedule.",
                "tips": "Quantify impact. Show leadership and technical skills.",
            },
            {
                "q": "How do you handle tight deadlines?",
                "a": "I prioritize tasks based on impact and dependencies, communicate proactively about blockers, and break work into manageable chunks. I've found that early communication prevents most deadline issues.",
                "tips": "Show planning and communication skills.",
            },
            {
                "q": "Describe your ideal work environment.",
                "a": "I thrive in collaborative environments with clear goals, regular feedback, and opportunities for learning. I enjoy working with diverse teams where knowledge sharing is encouraged.",
                "tips": "Be honest but align with company culture.",
            },
        ],
        "advanced": [
            {
                "q": "Tell me about a time you failed and what you learned.",
                "a": "I once deployed a feature without adequate testing that caused a production outage. I learned the importance of comprehensive testing, proper code review, and having rollback procedures. I now champion testing best practices.",
                "tips": "Show accountability and genuine learning.",
            },
            {
                "q": "How do you influence decisions without authority?",
                "a": "I build credibility through expertise and data. When proposing changes, I present evidence, anticipate concerns, and involve stakeholders early. I focus on shared goals rather than personal preferences.",
                "tips": "Demonstrate leadership and communication skills.",
            },
            {
                "q": "Describe your approach to mentoring junior developers.",
                "a": "I focus on creating a safe learning environment, providing constructive feedback, and gradually increasing responsibility. I pair program, review code thoroughly, and help them build problem-solving skills rather than just giving answers.",
                "tips": "Show patience and genuine investment in others' growth.",
            },
            {
                "q": "How do you stay current with technology trends?",
                "a": "I maintain a learning routine: reading technical blogs, attending meetups, experimenting with side projects, and contributing to open source. I also evaluate new technologies critically before adopting them.",
                "tips": "Show genuine passion for learning.",
            },
        ],
    },
    "hr": {
        "beginner": [
            {
                "q": "What are your salary expectations?",
                "a": "Based on my research and experience, I'm looking for a competitive salary in the range of market rates for this role. I'm open to discussing the total compensation package.",
                "tips": "Research market rates. Be flexible but informed.",
            },
            {
                "q": "When can you start?",
                "a": "I can provide a two-week notice period to my current employer, or I'm available to start immediately if needed. I'm flexible based on your team's requirements.",
                "tips": "Be honest about your timeline.",
            },
            {
                "q": "Are you willing to relocate?",
                "a": "I'm open to discussing relocation if the opportunity is the right fit. I'd want to understand the relocation support offered and the local area.",
                "tips": "Be honest about your preferences.",
            },
            {
                "q": "Do you have any questions for us?",
                "a": "Yes, I'd like to know more about the team structure, the technologies you use, and what success looks like in this role. I'm also curious about growth opportunities.",
                "tips": "Always have thoughtful questions prepared.",
            },
        ],
        "intermediate": [
            {
                "q": "Where do you see yourself in 5 years?",
                "a": "I see myself growing into a technical leadership role, mentoring others, and contributing to architecture decisions. I'm committed to continuous learning and taking on increasing responsibility.",
                "tips": "Show ambition aligned with the company's growth.",
            },
            {
                "q": "Why should we hire you?",
                "a": "I bring a combination of technical skills in {skills}, proven problem-solving abilities, and a track record of delivering results. I'm also a collaborative team member who communicates effectively.",
                "tips": "Highlight your unique value proposition.",
            },
            {
                "q": "How do you handle stress?",
                "a": "I manage stress by prioritizing tasks, taking breaks when needed, and maintaining work-life balance. I also find that clear communication and realistic planning reduce most stressors.",
                "tips": "Show healthy coping mechanisms.",
            },
            {
                "q": "What motivates you?",
                "a": "I'm motivated by solving complex problems, learning new technologies, and seeing the impact of my work on users. I also enjoy mentoring others and contributing to team success.",
                "tips": "Be genuine and specific.",
            },
        ],
        "advanced": [
            {
                "q": "How do you handle disagreement with management?",
                "a": "I express my perspective respectfully with data and reasoning, then commit fully to the decision once made. I've found that healthy disagreement leads to better outcomes when handled professionally.",
                "tips": "Show maturity and team orientation.",
            },
            {
                "q": "What's your approach to work-life balance?",
                "a": "I believe sustainable productivity comes from maintaining boundaries. I set clear work hours, take vacation time, and focus on efficiency during work hours rather than long hours.",
                "tips": "Be honest and show self-awareness.",
            },
            {
                "q": "How do you handle ambiguity in requirements?",
                "a": "I ask clarifying questions, make reasonable assumptions documented in writing, iterate quickly with stakeholders, and embrace change as a natural part of the development process.",
                "tips": "Show adaptability and communication skills.",
            },
            {
                "q": "Describe your leadership style.",
                "a": "I lead by example, empower team members, and focus on removing blockers. I believe in giving context rather than instructions, and creating an environment where people do their best work.",
                "tips": "Show genuine leadership philosophy.",
            },
        ],
    },
    "system_design": {
        "beginner": [
            {
                "q": "How would you design a URL shortener?",
                "a": "I'd use a hash function to generate short codes, store mappings in a database with TTL for expiration, implement a caching layer for popular URLs, and add analytics tracking for click data.",
                "tips": "Start simple, then add complexity. Consider scale.",
            },
            {
                "q": "Design a simple chat application.",
                "a": "I'd use WebSockets for real-time messaging, a message queue for reliability, a database for message history, and implement features like read receipts and typing indicators.",
                "tips": "Consider real-time requirements and scalability.",
            },
            {
                "q": "How would you design a notification system?",
                "a": "I'd create a notification service that accepts events, queues them for processing, and delivers via multiple channels (email, push, SMS). I'd include preference management and delivery tracking.",
                "tips": "Think about reliability and user preferences.",
            },
        ],
        "intermediate": [
            {
                "q": "Design a news feed system like Twitter.",
                "a": "I'd use a fan-out-on-write approach: when a user posts, push to all followers' feeds. I'd use a cache for hot feeds, a database for storage, and implement pagination and ranking algorithms.",
                "tips": "Consider read vs write optimization trade-offs.",
            },
            {
                "q": "How would you design a payment system?",
                "a": "I'd implement idempotent transactions, use a ledger for accounting, integrate with payment processors, handle webhooks for async updates, and ensure PCI compliance for card data.",
                "tips": "Security and reliability are paramount.",
            },
            {
                "q": "Design a real-time analytics dashboard.",
                "a": "I'd use event streaming (Kafka), time-series database for metrics, aggregation pipelines for real-time processing, and WebSockets for live updates to the frontend.",
                "tips": "Consider data volume and query patterns.",
            },
        ],
        "advanced": [
            {
                "q": "Design a distributed file storage system.",
                "a": "I'd implement chunking and replication, use consistent hashing for distribution, build a metadata service, handle failures with gossip protocol, and ensure strong consistency where needed.",
                "tips": "Think about fault tolerance and consistency models.",
            },
            {
                "q": "How would you design a rate limiter at scale?",
                "a": "I'd use a token bucket algorithm with Redis for distributed state, implement multiple rate limit tiers, handle clock skew, and ensure the system degrades gracefully under load.",
                "tips": "Consider distributed systems challenges.",
            },
            {
                "q": "Design a search engine indexing system.",
                "a": "I'd build an inverted index, implement document processing pipelines, use sharding for distribution, add caching for frequent queries, and implement relevance ranking algorithms.",
                "tips": "Think about indexing strategies and query performance.",
            },
        ],
    },
    "coding": {
        "beginner": [
            {
                "q": "Write a function to reverse a string.",
                "a": "def reverse_string(s): return s[::-1]\n\nThis uses Python slicing to reverse the string in O(n) time and O(1) space (or O(n) if creating a new string).",
                "tips": "Consider edge cases: empty string, single character.",
            },
            {
                "q": "Find the largest element in an array.",
                "a": "def find_largest(arr):\n    if not arr: return None\n    largest = arr[0]\n    for num in arr[1:]:\n        if num > largest: largest = num\n    return largest\n\nO(n) time, O(1) space.",
                "tips": "Handle edge cases. Discuss time complexity.",
            },
            {
                "q": "Check if a string is a palindrome.",
                "a": "def is_palindrome(s): return s == s[::-1]\n\nFor case-insensitive: s.lower() == s.lower()[::-1]\nO(n) time, O(1) space.",
                "tips": "Consider ignoring spaces and case.",
            },
        ],
        "intermediate": [
            {
                "q": "Implement a basic LRU cache.",
                "a": "Use OrderedDict or a doubly-linked list with hash map. Get/Put operations in O(1). Maintain access order, evict least recently used when capacity exceeded.",
                "tips": "Discuss trade-offs between approaches.",
            },
            {
                "q": "Merge two sorted arrays.",
                "a": "Use two pointers: compare elements from each array, add smaller to result. Handle remaining elements. O(n+m) time, O(n+m) space.",
                "tips": "Consider in-place vs new array approaches.",
            },
            {
                "q": "Find all duplicates in an array.",
                "a": "Use a set to track seen elements. When encountering an already-seen element, add to duplicates. O(n) time, O(n) space.",
                "tips": "Discuss space-time trade-offs.",
            },
        ],
        "advanced": [
            {
                "q": "Design a concurrent task scheduler.",
                "a": "Use a priority queue with thread pool. Implement task dependencies as a DAG, topological sort for execution order, and handle failures with retry logic.",
                "tips": "Consider concurrency primitives and failure handling.",
            },
            {
                "q": "Implement a distributed lock.",
                "a": "Use Redis with SET NX EX for atomic acquisition, implement fencing tokens for safety, handle network partitions with lease-based expiration.",
                "tips": "Discuss consistency and availability trade-offs.",
            },
            {
                "q": "Optimize a slow database query.",
                "a": "Analyze query plan, add appropriate indexes, consider denormalization, implement caching, evaluate query restructuring. Profile before and after.",
                "tips": "Show systematic approach to performance optimization.",
            },
        ],
    },
}


def generate_questions(
    role: str = "",
    skills: list[str] = None,
    resume_text: str = "",
    categories: list[str] = None,
    difficulty: str = "intermediate",
    count: int = 10,
) -> list[dict]:
    """
    Generate interview questions based on role, skills, and resume.

    Returns list of question dicts with:
        - category, difficulty, question, sample_answer, tips
    """
    if skills is None:
        skills = []
    if categories is None:
        categories = ["technical", "behavioral", "hr"]

    # Extract skills from resume if provided
    if resume_text:
        resume_skills = _extract_skills(resume_text)
        skills = list(set(skills + resume_skills))

    # Get skill names for templating
    skill1 = skills[0] if skills else "software development"
    skill2 = skills[1] if len(skills) > 1 else "web development"

    all_questions = []

    for category in categories:
        if category not in QUESTION_BANK:
            continue
        difficulty_questions = QUESTION_BANK[category].get(difficulty, [])
        for q_template in difficulty_questions:
            question = q_template["q"].format(
                skill=skill1,
                skill2=skill2,
                skills=", ".join(skills[:3]),
                industry=role or "technology",
            )
            answer = q_template["a"].format(
                skill=skill1,
                skill2=skill2,
                skills=", ".join(skills[:3]),
                industry=role or "technology",
            )
            all_questions.append(
                {
                    "category": category,
                    "difficulty": difficulty,
                    "question": question,
                    "sample_answer": answer,
                    "tips": q_template["tips"],
                }
            )

    # Shuffle and limit
    random.shuffle(all_questions)
    return all_questions[:count]
