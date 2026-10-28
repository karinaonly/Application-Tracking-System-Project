"""Curated skills taxonomy used by the keyword engine.

Each entry maps a canonical display name -> list of aliases/variants that should
count as the same skill. The canonical name itself is always matched too.

Rules of thumb when adding entries:
- Add real-world spellings people write on resumes/JDs ("Node.js", "NodeJS", "node").
- Avoid ambiguous 1-2 letter terms ("R", "C", "Go") -- they cause false matches.
  Use the unambiguous form instead ("Golang", "R programming").
- Matching is case-insensitive and word-boundary aware, so "Java" will NOT match
  "JavaScript", and "js" will NOT match inside "Node.js".
"""

import re

HARD_SKILLS: dict[str, list[str]] = {
    # ---- Languages ----
    "Python": [],
    "JavaScript": ["js", "ecmascript", "es6"],
    "TypeScript": ["ts"],
    "Java": [],
    "C#": ["c sharp", "csharp"],
    "C++": ["cpp"],
    "PHP": [],
    "Golang": [],
    "Rust": [],
    "Kotlin": [],
    "Swift": [],
    "Ruby": [],
    "SQL": [],
    "Bash": ["shell scripting", "shell script"],
    "R Programming": ["r language"],
    "HTML": ["html5"],
    "CSS": ["css3"],
    # ---- Frontend ----
    "React": ["react.js", "reactjs"],
    "Next.js": ["nextjs", "next js"],
    "Vue.js": ["vue", "vuejs"],
    "Angular": ["angularjs"],
    "Tailwind CSS": ["tailwind", "tailwindcss"],
    "Redux": [],
    "Bootstrap": [],
    "Vite": [],
    # ---- Backend / frameworks ----
    "Node.js": ["node", "nodejs", "node js"],
    "Express.js": ["expressjs", "express.js"],
    "FastAPI": ["fast api"],
    "Django": [],
    "Flask": [],
    "Spring Boot": ["springboot"],
    "Laravel": [],
    "ASP.NET": ["asp.net core", "aspnet"],
    ".NET": ["dotnet", "dot net"],
    "GraphQL": [],
    "REST API": ["rest apis", "restful", "restful api", "restful apis"],
    "Microservices": ["microservice"],
    "WebSockets": ["websocket"],
    # ---- Databases ----
    "PostgreSQL": ["postgres", "psql"],
    "MySQL": [],
    "SQLite": [],
    "MongoDB": ["mongo"],
    "Redis": [],
    "SQL Server": ["mssql", "ms sql", "microsoft sql server"],
    "Oracle": ["oracle db"],
    "Elasticsearch": ["elastic search"],
    "NoSQL": ["no-sql"],
    "SQLAlchemy": [],
    "SQLModel": [],
    "Firebase": [],
    "Supabase": [],
    # ---- Cloud / DevOps ----
    "AWS": ["amazon web services"],
    "Azure": ["microsoft azure"],
    "GCP": ["google cloud", "google cloud platform"],
    "Docker": ["dockerfile", "docker compose"],
    "Kubernetes": ["k8s"],
    "Terraform": [],
    "Ansible": [],
    "Jenkins": [],
    "GitHub Actions": ["gh actions"],
    "CI/CD": ["cicd", "ci cd", "continuous integration", "continuous delivery", "continuous deployment"],
    "Git": [],
    "GitHub": [],
    "GitLab": [],
    "Linux": [],
    "Nginx": [],
    "Serverless": ["aws lambda"],
    # ---- Data / ML ----
    "Machine Learning": ["ml"],
    "Deep Learning": [],
    "NLP": ["natural language processing"],
    "Pandas": [],
    "NumPy": [],
    "scikit-learn": ["sklearn", "scikit learn"],
    "TensorFlow": [],
    "PyTorch": [],
    "Data Analysis": ["data analytics", "data analyst"],
    "Data Visualization": ["data viz"],
    "Power BI": ["powerbi"],
    "Tableau": [],
    "Excel": ["microsoft excel", "ms excel"],
    "ETL": [],
    "Spark": ["apache spark", "pyspark"],
    "Airflow": ["apache airflow"],
    "Kafka": ["apache kafka"],
    "LLM": ["llms", "large language model", "large language models"],
    "OpenAI": [],
    "Prompt Engineering": [],
    # ---- Testing / quality ----
    "Unit Testing": ["unit tests", "unit test"],
    "Pytest": [],
    "Jest": [],
    "Selenium": [],
    "Cypress": [],
    "Postman": [],
    "TDD": ["test-driven development", "test driven development"],
    # ---- Security / auth ----
    "JWT": ["json web token", "json web tokens"],
    "OAuth": ["oauth2", "oauth 2.0"],
    "Authentication": ["authn"],
    "Authorization": ["authz"],
    # ---- Process / tools ----
    "Agile": [],
    "Scrum": [],
    "Kanban": [],
    "Jira": [],
    "Figma": [],
    "Confluence": [],
    "Swagger": ["openapi"],
    "System Design": ["software architecture"],
    "Object-Oriented Programming": ["oop", "object oriented programming", "object oriented"],
    "Design Patterns": [],
    "API Development": ["api design", "api integration"],
    # ---- Mobile ----
    "Android": [],
    "iOS": [],
    "React Native": [],
    "Flutter": [],
    # ---- General business / non-tech (kept small; extend for your target roles) ----
    "Project Management": [],
    "Customer Service": ["customer support", "client service"],
    "Data Entry": [],
    "Microsoft Office": ["ms office", "office suite"],
    "Salesforce": [],
    "SEO": ["search engine optimization"],
    "Content Writing": ["copywriting"],
    "Quality Assurance": ["qa"],
    "Bookkeeping": [],
    "Budgeting": [],
}


SOFT_SKILL_GROUPS: dict[str, list[str]] = {
  "Communication": ["communication skills", "communicate", "communicating", "clear communication", "verbal communication", "written communication"],
  "Leadership": [],
  "Teamwork": ["team player", "team work", "collaboration", "collaborative", "collaborating", "collaborate", "collaborated", "work in a team"],
  "Problem Solving": ["problem-solving"],
  "Critical Thinking": [],
  "Time Management": [],
  "Adaptability": [],
  "Creativity": [],
  "Attention To Detail": ["attention to detail", "detail-oriented"],
  "Analytical": ["analytical skills"],
  "Strategic Thinking": [],
  "Mentoring": ["coaching"],
  "Negotiation": [],
  "Presentation": [],
  "Public Speaking": [],
  "Decision Making": [],
  "Conflict Resolution": [],
  "Emotional Intelligence": [],
  "Self-Motivated": [],
  "Proactive": [],
  "Innovative": [],
  "Organizational": [],
  "Multitasking": [],
  "Interpersonal": [],
  "Cross-Functional": [],
  "Stakeholder Management": [],
  "Continuous Learning": ["eager to learn", "willingness to learn", "willing to learn", "quick learner", "fast learner", "lifelong learning", "professional growth", "professional development"],
  "Client Coordination": ["coordinate with clients", "coordinating with clients", "client communication", "client-facing", "client facing"],
  "Knowledge Sharing": ["share knowledge", "sharing knowledge", "teach", "teaching", "training materials", "technical talks", "short talks"],
}


# Canonical names whose *canonical spelling* is also an everyday English word.
# For these, the canonical form is matched case-sensitively ("Excel", not "excel at...").
# Their aliases (e.g. "ms excel") are still matched case-insensitively.
CASE_SENSITIVE: set[str] = {"Excel", "Swift", "Spark", "Oracle", "Ruby", "Rust"}


# ---------------------------------------------------------------------------
# Skill categories (A3 refinement)
# ---------------------------------------------------------------------------
# Confirmed keywords are folded into the matching labeled line of the resume's
# skills section ("Databases: MySQL, SQL") instead of a bolted-on list. Skills
# not covered here fall back to the "Additional Skills" line. A consistency
# test asserts this mapping covers every HARD_SKILLS entry exactly once.
HARD_SKILL_CATEGORIES: dict[str, list[str]] = {
    "Languages": [
        "Python", "JavaScript", "TypeScript", "Java", "C#", "C++", "PHP",
        "Golang", "Rust", "Kotlin", "Swift", "Ruby", "Bash", "R Programming",
    ],
    "Frontend": [
        "HTML", "CSS", "React", "Next.js", "Vue.js", "Angular",
        "Tailwind CSS", "Redux", "Bootstrap", "Vite",
    ],
    "Backend": [
        "Node.js", "Express.js", "FastAPI", "Django", "Flask", "Spring Boot",
        "Laravel", "ASP.NET", ".NET", "GraphQL", "REST API", "Microservices",
        "WebSockets", "API Development",
    ],
    "Databases": [
        "SQL", "PostgreSQL", "MySQL", "SQLite", "MongoDB", "Redis",
        "SQL Server", "Oracle", "Elasticsearch", "NoSQL", "SQLAlchemy",
        "SQLModel", "Firebase", "Supabase",
    ],
    "Cloud & DevOps": [
        "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "Ansible",
        "Jenkins", "GitHub Actions", "CI/CD", "Git", "GitHub", "GitLab",
        "Linux", "Nginx", "Serverless",
    ],
    "Data & ML": [
        "Machine Learning", "Deep Learning", "NLP", "Pandas", "NumPy",
        "scikit-learn", "TensorFlow", "PyTorch", "Data Analysis",
        "Data Visualization", "Power BI", "Tableau", "Excel", "ETL", "Spark",
        "Airflow", "Kafka", "LLM", "OpenAI", "Prompt Engineering",
    ],
    "Testing": [
        "Unit Testing", "Pytest", "Jest", "Selenium", "Cypress", "Postman",
        "TDD", "Quality Assurance",
    ],
    "Security": ["JWT", "OAuth", "Authentication", "Authorization"],
    # Paradigms and methodologies are not tools. Keeping them out of
    # "Process & Tools" matters because that category's label keywords include
    # the generic word "tools", which otherwise matches a resume line like
    # "DevOps & Tools" and files OOP under DevOps (caught live).
    "Concepts": [
        "Object-Oriented Programming", "Design Patterns", "System Design",
        "Agile", "Scrum", "Kanban",
    ],
    "Process & Tools": ["Jira", "Confluence", "Swagger", "Figma"],
    "Mobile": ["Android", "iOS", "React Native", "Flutter"],
    "Business": [
        "Project Management", "Customer Service", "Data Entry",
        "Microsoft Office", "Salesforce", "SEO", "Content Writing",
        "Bookkeeping", "Budgeting",
    ],
}

SKILL_CATEGORY_LOOKUP: dict[str, str] = {
    name.lower(): category
    for category, names in HARD_SKILL_CATEGORIES.items()
    for name in names
}

# Words that identify a resume's own skills label as one of our categories.
# Matching is whole-word and per-category, so "DevOps & Tools" can accept both
# Cloud & DevOps skills and the tools that belong to Process & Tools. Generic
# words ("tools") must NOT appear in a category that would otherwise swallow
# unrelated skills: "tools" is what used to file OOP under "DevOps & Tools".
CATEGORY_LABEL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Languages": ("language", "languages", "programming"),
    "Frontend": ("frontend", "front end", "ui", "client side", "web"),
    "Backend": ("backend", "back end", "server", "framework", "frameworks",
                "api", "apis", "orm", "orms"),
    "Databases": ("database", "databases", "db", "storage"),
    # No "tools"/"tooling" here: "DevOps & Tools" already matches via "devops",
    # and owning the generic word made every tool-looking label cloud-related.
    "Cloud & DevOps": ("cloud", "devops", "dev ops", "infrastructure",
                       "version control", "ci/cd", "platform"),
    "Data & ML": ("data", "analytics", "machine learning", "ml", "ai"),
    "Testing": ("testing", "test", "qa", "quality"),
    "Security": ("security", "auth", "authentication", "authorization"),
    "Concepts": ("concept", "concepts", "principle", "principles", "paradigm",
                 "methodology", "methodologies", "practices", "agile",
                 "scrum", "kanban"),
    "Process & Tools": ("process", "processes", "tools", "tooling", "project"),
    "Mobile": ("mobile", "android", "ios"),
    "Business": ("business", "general", "soft"),
}

_SOFT_NAME_LOOKUP: set[str] = {name.lower() for name in SOFT_SKILL_GROUPS} | {
    alias.lower()
    for aliases in SOFT_SKILL_GROUPS.values()
    for alias in aliases
}


def skill_category(name: str) -> str | None:
    """Category for a canonical skill name, or None when not in the taxonomy."""
    return SKILL_CATEGORY_LOOKUP.get(name.strip().lower())


def is_soft_skill(name: str) -> bool:
    """True for soft skills (Communication, Leadership, ...) and their aliases.

    Soft skills are NOT added to a resume's skills list: a list of adjectives is
    unverifiable and reads like keyword stuffing. They belong in bullets.
    """
    return name.strip().lower() in _SOFT_NAME_LOOKUP


def label_matches_category(label: str, category: str) -> bool:
    """True when a resume's own skills label ("Databases", "DevOps & Tools")
    identifies the given category."""
    keywords = CATEGORY_LABEL_KEYWORDS.get(category, ())
    if not keywords:
        return False
    norm = re.sub(r"[^a-z0-9&/ ]+", " ", label.lower())
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", norm)
        for word in keywords
    )
