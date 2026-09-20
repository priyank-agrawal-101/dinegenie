"""Credential-free deterministic fake. Never selected through production configuration."""

import json

from app.llm.contracts import ModelError, ModelPrompt, ModelReply


class FakeRecommendationModel:
    def __init__(self, replies: list[ModelReply | ModelError] | None = None):
        self.replies = list(replies or [])
        self.calls: list[ModelPrompt] = []

    async def rank_and_explain(self, prompt: ModelPrompt) -> ModelReply:
        self.calls.append(prompt)
        if self.replies:
            reply = self.replies.pop(0)
            if isinstance(reply, ModelError):
                raise reply
            return reply
        data = json.loads(prompt.user)
        selected = data["candidates"][: data["result_count"]]
        return ModelReply(
            json.dumps(
                {
                    "recommendations": [
                        {
                            "restaurant_id": item["restaurant_id"],
                            "explanation": " ".join(item["allowed_sentences"][:2]),
                            "matched_preferences": item["matched_preferences"],
                            "unverified_preferences": item["unverified_preferences"],
                        }
                        for item in selected
                    ],
                    "summary": None,
                }
            ),
            "fake-grounded-v1",
            0,
            0,
        )
