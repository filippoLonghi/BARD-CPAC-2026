class SentenceDisplay { // gestisce la singola frase, spazio e animazione
  ArrayList<FlyingWord> words = new ArrayList<FlyingWord>();
  int sceneStartedAt;
  int slotStartMs;
  int assembleEndMs;
  int slotEndMs;
  
  int nextWordIndex = 0;
  float opacity = 0;
  boolean started = false;
  boolean assembled = false;
  
  int flightBufferMs = 2000; // stima di tempo che ha l'ultima parola per sistemarsi così che possa stare stabile per il stableMs

  SentenceDisplay(String sentence, int sceneStart, int startOffsetMs, int assemblyOffsetMs, int endOffsetMs, int layoutIndex) {
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

    int totalTimeForAssembly = assembleEndMs - slotStartMs; 
    int spawnDuration = max(100, totalTimeForAssembly - flightBufferMs); // tempo che ha di lancio parola
    
    float progress = constrain((elapsed - slotStartMs) / (float)spawnDuration, 0, 1);
    
    int shouldBeActive = min(words.size(), ceil(progress * words.size())); // divisione fattta strana per dire ogni quanto deve partire una parola
    
    while (nextWordIndex < shouldBeActive) {
      words.get(nextWordIndex).active = true;
      nextWordIndex++;
    }

    for (FlyingWord word : words) {
      if (word.active) word.update();
    }

    /*// The scene deadline is authoritative. Physical travel may vary by screen size,
    // so snap unfinished words into place before the guaranteed reading interval.
    if (!assembled && elapsed >= assembleEndMs) {
      for (FlyingWord word : words) {
        word.active = true;
        word.lockToTarget();
      }
      nextWordIndex = words.size();
      assembled = true;
    }*/

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
