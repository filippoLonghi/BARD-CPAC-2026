from __future__ import annotations

from ..config import BardSettings
from ..contracts import MOOD_LABELS, MusicSegment, StoryFragment
from ..utils import extract_json

def generate_story_with_gemini(
    segments: list[MusicSegment],
    settings: BardSettings,
    words_per_fragment: int,
) -> tuple[list[StoryFragment], str]:
    if not settings.gcp_project_id:
        raise RuntimeError("Set BARD_GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT before using Vertex story generation.")

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Vertex story generation requires `pip install -e .[cloud]`.") from exc

    apiClient = genai.Client(vertexai=True, project=settings.gcp_project_id, location=settings.gcp_location)
    
    totalSegmentsCount = len(segments)
    generatedStorySoFar = ""
    storyFragmentsList: list[StoryFragment] = []

    for currentIndex, currentSegment in enumerate(segments):
        # 1. Narrative phase calculation (Now in English)
        if currentIndex == 0:
            narrativePhase = "BEGINNING: Introduce the abstract world, the mystery, or the main presence. Establish the opening."
        elif currentIndex == totalSegmentsCount - 1:
            narrativePhase = "ENDING: Resolve the narrative tension, conclude the journey, and write the definitive ending of the story."
        else:
            narrativePhase = "MIDDLE: Develop the plot based on previous events, maintaining high consistency."

        # 2. Dynamic Prompt (Fully in English)
        dynamicPrompt = f"""
BARD is an after-score: it gives visible narrative form to one unique human performance.
You are generating a story piece by piece. 

Rules:
- Return JSON only.
- Write EXACTLY one fragment of about {words_per_fragment} words, ending with a complete sentence.
- Do not mention instruments, recording technology, audio analysis, Gemini, or AI.
- You must STRICTLY continue the narrative from the "Story Generated So Far". Keep the same world and entities.

Current State:
- Current segment: {currentIndex + 1} of {totalSegmentsCount}.
- Narrative phase: {narrativePhase}.

Music emotional timeline for this segment:
time={currentSegment.start_s}-{currentSegment.end_s}, mood_hint={currentSegment.mood_hint}, feeling={currentSegment.music_prompt}

Story Generated So Far (You MUST continue from here without repeating what has already been said):
{generatedStorySoFar if generatedStorySoFar else "[No previous story. Start now.]"}
"""
        
        # 3. Iterative API Call
        apiResponse = apiClient.models.generate_content(
            model=settings.vertex_text_model,
            contents=dynamicPrompt,
            config=types.GenerateContentConfig(
                temperature=0.75,
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "mood": {"type": "STRING", "enum": MOOD_LABELS},
                        "text": {"type": "STRING"},
                        "image_prompt": {"type": "STRING"},
                        "visual_motif": {"type": "STRING"},
                        "palette": {"type": "STRING"},
                        "motion": {"type": "STRING"},
                    },
                    "required": ["mood", "text"],
                },
            ),
        )
        
        parsedJson = extract_json(apiResponse.text or "{}")
        cleanedText = " ".join(str(parsedJson.get("text", "")).split())
        
        # 4. Contextual Update
        if generatedStorySoFar:
            generatedStorySoFar += "\n\n" + cleanedText
        else:
            generatedStorySoFar = cleanedText

        # 5. Safe fragment creation restoring original contract parameters
        storyFragmentsList.append(
            StoryFragment(
                id=currentSegment.id,
                mood=str(parsedJson.get("mood", currentSegment.mood_hint if currentSegment else "CALM")).upper(),
                text=cleanedText,
                music_prompt=currentSegment.music_prompt if currentSegment else None,
                start_s=currentSegment.start_s if currentSegment else None,
                end_s=currentSegment.end_s if currentSegment else None,
                image_prompt=parsedJson.get("image_prompt"),
                visual_motif=parsedJson.get("visual_motif"),
                palette=parsedJson.get("palette"),
                motion=parsedJson.get("motion"),
            )
        )

    fullStory = generatedStorySoFar.strip()
    return storyFragmentsList, fullStory