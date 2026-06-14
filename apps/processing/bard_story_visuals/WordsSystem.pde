class SentenceDisplay {
  ArrayList<FlyingWord> words = new ArrayList<FlyingWord>();
  int sceneStartedAt;
  int slotStartMs;
  int assembleEndMs;
  int slotEndMs;
  int nextWordIndex = 0;
  float opacity = 0;
  boolean started = false;
  boolean assembled = false;

  SentenceDisplay(
    String sentence,
    int sceneStart,
    int startOffsetMs,
    int assemblyOffsetMs,
    int endOffsetMs,
    int layoutIndex
  ) {
    sceneStartedAt = sceneStart;
    slotStartMs = startOffsetMs;
    assembleEndMs = max(startOffsetMs + 1, assemblyOffsetMs);
    slotEndMs = max(assembleEndMs + 1, endOffsetMs);
    layoutSentence(sentence, layoutIndex);
  }

  void layoutSentence(String sentence, int layoutIndex) {
    textSize(fontSize);
    float boxW = width * random(0.34f, 0.50f);
    int column = layoutIndex % 2;
    int row = (layoutIndex / 2) % 3;
    float x = column == 0 ? width * 0.08f : width * 0.52f;
    x += random(-width * 0.025f, width * 0.025f);
    float y = height * (0.18f + row * 0.25f) + random(-24, 24);
    float lineX = x;
    float lineY = y;

    String[] rawWords = splitTokens(sentence, " \t\n\r");
    for (String word : rawWords) {
      float wordW = textWidth(word + " ");
      if (lineX + wordW > x + boxW) {
        lineX = x;
        lineY += leading;
      }
      words.add(new FlyingWord(word, lineX, lineY, layoutIndex));
      lineX += wordW;
    }
  }

  void update() {
    int elapsed = millis() - sceneStartedAt;
    if (elapsed < slotStartMs) return;
    started = true;
    opacity = min(255, opacity + 18);

    int assemblyDuration = max(1, assembleEndMs - slotStartMs);
    float progress = constrain((elapsed - slotStartMs) / (float)assemblyDuration, 0, 1);
    int shouldBeActive = min(words.size(), ceil(progress * words.size()));
    while (nextWordIndex < shouldBeActive) {
      words.get(nextWordIndex).active = true;
      nextWordIndex++;
    }

    for (FlyingWord word : words) {
      if (word.active) word.update();
    }

    // The scene deadline is authoritative. Physical travel may vary by screen size,
    // so snap unfinished words into place before the guaranteed reading interval.
    if (!assembled && elapsed >= assembleEndMs) {
      for (FlyingWord word : words) {
        word.active = true;
        word.lockToTarget();
      }
      nextWordIndex = words.size();
      assembled = true;
    }

    if (elapsed >= slotEndMs) {
      opacity = max(0, opacity - 22);
    }
  }

  void draw(Atmosphere atmosphere) {
    if (!started) return;
    for (FlyingWord word : words) {
      word.opacity = opacity;
      if (word.active) word.displayBase(atmosphere.textColor, atmosphere.glowColor);
    }
  }

  boolean isInvisibleAndFinished() {
    return millis() - sceneStartedAt >= slotEndMs && opacity <= 1;
  }
}


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
      int slotMs = max(1, slotEnd - cursorMs);

      // Reserve a real stable-reading interval. Short sentences assemble faster;
      // long sentences keep up to 22% of their proportional slot for reading.
      int stableMs = constrain(round(slotMs * 0.22f), 1200, 2400);
      stableMs = min(stableMs, max(1, slotMs - 100));
      int assemblyMs = max(1, slotMs - stableMs);
      scheduled.add(
        new SentenceDisplay(
          sentences.get(index),
          sceneStart,
          cursorMs,
          cursorMs + assemblyMs,
          slotEnd,
          sentenceCounter
        )
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
