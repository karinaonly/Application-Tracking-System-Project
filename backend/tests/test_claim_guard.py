import unittest

from app.analyzer.claim_guard import check_rewrite, describe_violations


O_SCHEMA = "Built backend schemas, data logic, and GraphQL APIs for the Omega E-Commerce System to handle product, order, and user data."
O_DOCKER = "Deployed and containerized full-stack projects using Docker, Nginx, and VPS, ensuring consistent environments and keep production sites running smoothly."
O_EXAM = "Led end-to-end development of a secure web-based exam platform using React.js, NestJS, and MySQL, delivering a fully functional system for student exams."
O_PROCTOR = "Implemented real-time proctoring features using WebSockets and integrated RESTful APIs to prevent cheating and ensure reliable data sync between the frontend and backend."
O_GIT = "Managed the team's Git workflow, which cut down on merge conflicts and kept the development process organized."
O_PAYROLL = "Led a 5-member team to build an internal payroll system using PHP and MySQL, automating payroll calculations and centralizing employee records."
O_GAME = "Built an arcade-style game on Arduino Uno using C++, writing the logic for player movement, collision detection, and real-time score tracking."
O_HW = "Collaborated with a 5-member team to assemble the hardware, wiring the circuit components to respond correctly to the C++ game logic."


class ClaimGuardTests(unittest.TestCase):
    def assert_passes(self, original, rewrite):
        self.assertEqual(check_rewrite(original, rewrite), [])

    def assert_fails_with(self, original, rewrite, code):
        codes = {item[0] for item in check_rewrite(original, rewrite)}
        self.assertIn(code, codes)

    def test_must_pass_cases(self):
        cases = [
            (O_SCHEMA, "Developed backend schemas, data logic, and GraphQL APIs for the Omega E-Commerce System to manage product, order, and user data."),
            (O_PAYROLL, "Led a 5-member team in building an internal payroll system with PHP and MySQL, automating payroll calculations and centralizing employee records."),
            (O_GIT, "Managed the team's Git workflow through clear communication, reducing merge conflicts and keeping the development process organized."),
            ("Helped the team migrate services", "Supported the team in migrating services"),
            (O_GAME, "Developed an arcade-style game on Arduino Uno using C++, implementing player movement, collision detection, and real-time score tracking logic."),
            ("Reduced load time by 40%", "Reduced page load time by 40%"),
            ("Built the [Capstone] exam platform using React.js", "Developed the [Capstone] exam platform using React.js"),
            (O_EXAM, "Directed end-to-end development of a secure web-based exam platform using React.js, NestJS, and MySQL, delivering a fully functional system for student exams."),
            (O_EXAM, "Spearheaded end-to-end development of a secure web-based exam platform using React.js, NestJS, and MySQL, delivering a fully functional system for student exams."),
            (O_HW, "Collaborated with a five-member team to assemble the hardware, wiring the circuit components to respond correctly to the C++ game logic."),
        ]
        for original, rewrite in cases:
            with self.subTest(rewrite=rewrite):
                self.assert_passes(original, rewrite)

    def test_must_fail_cases(self):
        cases = [
            (O_SCHEMA, "Architected backend schemas, data logic, and GraphQL APIs for the Omega E-Commerce System to handle product, order, and user data.", "verb_inflation"),
            (O_SCHEMA, "Engineered robust backend schemas, data logic, and GraphQL APIs for the Omega E-Commerce System, accelerating data transactions across products, orders, and users.", "claim_word"),
            (O_DOCKER, "Automated containerization and deployment pipelines for full-stack systems using Docker, Nginx, and VPS, ensuring uniform environments.", "claim_word"),
            (O_EXAM, "Led end-to-end development of a secure web-based exam platform using React.js, NestJS, and MySQL, deploying a production-ready solution for student exams.", "claim_word"),
            (O_PROCTOR, "Implemented real-time proctoring features using WebSockets and integrated RESTful APIs, guaranteeing reliable data synchronization between frontend and backend.", "claim_word"),
            (O_GIT, "Standardized team Git workflows, cutting merge conflict resolution time and streamlining collaboration.", "claim_word"),
            ("Reduced load time by 40%", "Reduced load time by 60%", "new_number"),
            ("Built a REST API with Python", "Built a REST API with Python and Docker", "new_skill"),
            ("Helped the team migrate services", "Led the migration of services", "verb_inflation"),
            ("Built the [Capstone] exam platform using React.js", "Developed the [Capstone] exam platform using React.js, serving [X] students", "placeholder"),
            ("Improved uptime", "Improved uptime by XX%", "placeholder"),
            ("Handled customer tickets", "Handled customer tickets for ___ clients", "placeholder"),
            ("Collaborated with a team to assemble hardware", "Collaborated with a five-member team to assemble hardware", "new_number"),
            ("Built a web app", "Built a web app serving thousands of users", "new_number"),
        ]
        for original, rewrite, code in cases:
            with self.subTest(rewrite=rewrite):
                self.assert_fails_with(original, rewrite, code)

    def test_description_and_lead_verb_edges(self):
        self.assert_fails_with("• Built a web app", "• Architected a web app", "verb_inflation")
        self.assert_passes("Engineered a service", "Architected a service")
        self.assert_passes("Built a web app", "• Built a web app")

    def test_implied_skills_and_new_proper_nouns(self):
        passing = [
            ("Implemented real-time proctoring features using WebSockets and integrated RESTful APIs to prevent cheating and ensure reliable data sync between the frontend and backend.", "Implemented real-time proctoring features with WebSockets and RESTful API integration to prevent cheating and keep data consistent."),
            ("Implemented real-time proctoring features using WebSockets and integrated RESTful APIs to prevent cheating.", "Implemented real-time proctoring using WebSockets and REST APIs to deter cheating."),
            ("Built a web app with React.js and Node.js", "Developed a web app using React and NodeJS"),
            ("Used Next.js and Tailwind for the portfolio site", "Built the portfolio site with NextJS and TailwindCSS"),
            ("Secured the API with JWT", "Secured the API with JWT authentication"),
            ("Wrote Jest tests for the checkout flow", "Wrote unit tests with Jest for the checkout flow"),
            (
                "Backend developer who ships APIs.",
                "Backend developer who ships reliable APIs. Focused on clean, maintainable code.",
            ),
        ]
        for original, rewrite in passing:
            with self.subTest(rewrite=rewrite):
                self.assert_passes(original, rewrite)

        failing = [
            ("Built backend schemas and GraphQL APIs for the Omega E-Commerce System", "Built backend schemas and GraphQL APIs using Prisma ORM for the Omega E-Commerce System", "new_proper_noun"),
            ("Deployed full-stack projects using Docker, Nginx, and VPS", "Deployed full-stack projects using Docker, Nginx, and VPS on Vercel", "new_proper_noun"),
            ("Built an app", "Built an app with Stripe and Firebase", "new_proper_noun"),
            ("Built a REST API", "Built a REST API with authentication", "new_skill"),
        ]
        for original, rewrite, code in failing:
            with self.subTest(rewrite=rewrite):
                self.assert_fails_with(original, rewrite, code)


if __name__ == "__main__":
    unittest.main()
