from app.services.llm.base import LLMResult


class MockLLMProvider:
    async def generate(self, messages: list[dict[str, str]], **kwargs: object) -> LLMResult:
        _ = kwargs
        _ = " ".join(message.get("content", "") for message in messages)
        system = messages[0].get("content", "") if messages else ""
        if "candidate profile" in system.lower():
            text = '{"name":null,"education":[],"skills":["Python"],"programming_languages":["Python"],"frameworks":[],"projects":[],"internships":[],"experience":[],"certifications":[],"achievements":[]}'
        elif "job requirements" in system.lower():
            text = '{"required_skills":["Python"],"preferred_skills":[],"technical_topics":["Machine Learning"],"responsibilities":[],"experience_requirements":[],"interview_topics":["Technical fundamentals"]}'
        elif "evaluate the answer" in system.lower():
            text = '{"technical_accuracy":75,"communication":78,"depth":70,"relevance":82,"problem_solving":72,"overall_score":75,"strengths":["Clear connection to experience."],"weaknesses":["Add measurable outcomes."],"feedback":"Solid answer with room for more detail.","recommended_followup":"What trade-off would you revisit?"}'
        elif "summarize the completed interview" in system.lower():
            text = '{"overall_score":75,"summary":"A solid interview with clear communication and useful technical reasoning.","strengths":["Clear communication"],"weaknesses":["Add measurable outcomes"],"recommended_practice":["Practice structured technical answers"]}'
        else:
            text = '{"question":"Tell me about a project that best demonstrates your experience for this role.","category":"Technical","difficulty":"Intermediate","rationale":"Based on the target role."}'
        return LLMResult(text=text, input_tokens=0, output_tokens=0, model="mock", provider="mock", latency_ms=0)

    async def health(self) -> bool:
        return True
