import json

from app.services.llm.base import LLMResult


class MockLLMProvider:
    async def generate(self, messages: list[dict[str, str]], **kwargs: object) -> LLMResult:
        _ = kwargs
        prompt = " ".join(message.get("content", "") for message in messages)
        system = messages[0].get("content", "") if messages else ""
        lower_prompt = prompt.lower()

        if "candidate profile" in system.lower():
            text = '{"name":null,"education":[],"skills":["Python"],"programming_languages":["Python"],"frameworks":[],"projects":[],"internships":[],"experience":[],"certifications":[],"achievements":[]}'
        elif "job requirements" in system.lower():
            text = '{"required_skills":["Python"],"preferred_skills":[],"technical_topics":["Machine Learning"],"responsibilities":[],"experience_requirements":[],"interview_topics":["Technical fundamentals"]}'
        elif "evaluate the answer" in system.lower():
            technical = 82 if "design" in lower_prompt or "architecture" in lower_prompt else 74
            communication = 80 if "clear" in lower_prompt or "explain" in lower_prompt else 72
            depth = 76 if "project" in lower_prompt or "measure" in lower_prompt else 68
            relevance = 88 if "role" in lower_prompt or "experience" in lower_prompt else 80
            problem_solving = 79 if "trade" in lower_prompt or "decision" in lower_prompt else 70
            overall = round((technical + communication + depth + relevance + problem_solving) / 5)
            text = (
                '{"technical_accuracy":' + str(technical) + ',"communication":' + str(communication) + ',"depth":' + str(depth) + ',"relevance":' + str(relevance) + ',"problem_solving":' + str(problem_solving) + ',"overall_score":' + str(overall) + ',"strengths":["The answer connected the example to measurable business impact.","The response stayed focused on the role and demonstrated a structured approach."],"weaknesses":["Adding a clearer trade-off analysis would strengthen the answer.","Quantifying the outcome with metrics would improve credibility."],"feedback":"The answer showed good structure and relevant examples, with room to sharpen the impact and trade-off discussion.","recommended_followup":"Describe the key metrics you used and how you decided between options."}'
            )
        elif "analyze the full interview" in system.lower() or "question by question" in system.lower() or "summarize the completed interview" in system.lower():
            words = [token for token in lower_prompt.replace("question", " ").replace("answer", " ").split() if len(token) > 4]
            unique = sorted(set(words))[:10]
            score = max(58, min(96, 62 + min(len(unique), 18) + (1 if "project" in lower_prompt else 0) + (1 if "metric" in lower_prompt else 0)))
            strengths = [
                "The candidate explained concrete examples tied to real work and outcomes.",
                "The answers were structured and easy to follow, which helped the reasoning come across clearly.",
                "The candidate referenced trade-offs and impact in ways that matched the job requirements."
            ]
            improvements = [
                "Add more quantifiable examples to reinforce the business impact of the work.",
                "Use a tighter structure for problem framing before jumping into the solution.",
                "Discuss decision trade-offs with more detail to show senior-level judgment."
            ]
            recommended = [
                "Practice STAR answers with metrics.",
                "Review system design trade-offs in depth.",
                "Prepare structured examples around ownership and impact."
            ]
            summary = f"The candidate showed a consistent ability to discuss goals, trade-offs, and relevant experience with clear structure. The interview quality was strongest when examples included metrics and explicit decisions, so tightening those details would raise the overall score further."
            text = '{"overall_score":' + str(int(score)) + ',"summary":' + json.dumps(summary) + ',"strengths":' + json.dumps(strengths[:3]) + ',"weaknesses":' + json.dumps(improvements[:3]) + ',"recommended_practice":' + json.dumps(recommended[:3]) + '}'
        else:
            if "Current question number: 1" in prompt:
                question = "Hi Candidate, welcome. Thanks for joining today. Take a moment to settle in - no rush. Tell me about a project that best demonstrates your experience for this role?"
            elif "Current question number: 2" in prompt:
                question = "Thanks for sharing that. Let's move on to a technical challenge you faced. How did you measure whether your solution worked?"
            else:
                question = "That's a helpful example. For our final question, what trade-off would you revisit in that work?"
            text = f'{{"question":"{question}","category":"Technical","difficulty":"Intermediate","rationale":"Based on the interview context."}}'
        return LLMResult(text=text, input_tokens=0, output_tokens=0, model="mock", provider="mock", latency_ms=0)

    async def health(self) -> bool:
        return True
