final float SENTENCE_STABLE_FRACTION = 0.35f;
final int SENTENCE_MIN_STABLE_MS = 1200;
final int SENTENCE_MAX_STABLE_MS = 4000;
final int SENTENCE_FLIGHT_BUFFER_MS = 3000;

class WordsSystem {
  ArrayList<SentenceDisplay> scheduled = new ArrayList<SentenceDisplay>();
  int sentenceCounter = 0;

  void beginScene(String textValue, float durationSeconds) {
    scheduled.clear();
    if (textValue == null || textValue.trim().length() == 0) return;

    String[] rawSentences = textValue.trim().split("(?<=[.!?])\\s+");
    ArrayList<String> sentences = new ArrayList<String>();
    ArrayList<Integer> wordCounts = new ArrayList<Integer>();
    int totalWords = 0;
    
    for (String sentence : rawSentences) {
      String cleaned = sentence.trim();
      if (cleaned.length() == 0) continue;
      int count = max(1, splitTokens(cleaned, " \t\n\r").length);
      sentences.add(cleaned);
      wordCounts.add(count);
      totalWords += count;
    }
    if (sentences.size() == 0) return;

    int sceneStart = millis();
    int totalMs = max(1000, round(durationSeconds * 1000.0f));
    int cursorMs = 0;
    int cumulativeWords = 0;
    
    for (int index = 0; index < sentences.size(); index++) {
      cumulativeWords += wordCounts.get(index);
      int slotEnd = index == sentences.size() - 1
        ? totalMs
        : round(totalMs * cumulativeWords / (float)totalWords);
      int slotMs = max(1, slotEnd - cursorMs); // slot ms prende una frazione di tempo per ogni frase basata su quante parole ha rispetto a tutto il segmento di storia

      // Reserve a real stable-reading interval. Short sentences assemble faster;
      // long sentences keep up to 22% of their proportional slot for reading.
      int stableMs = constrain(
        round(slotMs * SENTENCE_STABLE_FRACTION),
        SENTENCE_MIN_STABLE_MS,
        SENTENCE_MAX_STABLE_MS
      ); // tempo di lettura in cui le parole stan ferme
      stableMs = min(stableMs, max(1, slotMs - 100));
      int assemblyMs = max(1, slotMs - stableMs); // tempo in cui le parole si assemblano
      scheduled.add(
        new SentenceDisplay(sentences.get(index), sceneStart, cursorMs,
          cursorMs + assemblyMs, slotEnd, sentenceCounter)
      );
      sentenceCounter++;
      cursorMs = slotEnd;
    }
  }

  void updateWordLogic() {
    for (int index = scheduled.size() - 1; index >= 0; index--) {
      SentenceDisplay sentence = scheduled.get(index);
      sentence.update();
      if (sentence.isInvisibleAndFinished()) scheduled.remove(index);
    }
  }

  void drawWords(Atmosphere atmosphere) {
    blendMode(BLEND);
    for (SentenceDisplay sentence : scheduled) sentence.draw(atmosphere);
  }
}
