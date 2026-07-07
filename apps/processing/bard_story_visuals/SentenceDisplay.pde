class SentenceDisplay { /* gestisce la singola frase, spazio e animazione
  le frasi sono mandate da WordSystem, poi SentenceDisplay manda le FlyingWords*/
  ArrayList<FlyingWord> words = new ArrayList<FlyingWord>();
  int sceneStartedAt;
  int slotStartMs;
  int assembleEndMs;
  int slotEndMs;
  
  float opacity = 0;
  boolean started = false;
  
  int flightBufferMs = SENTENCE_FLIGHT_BUFFER_MS; // stima di tempo che ha l'ultima parola per sistemarsi così che possa stare stabile per il stableMs

  SentenceDisplay(String sentence, int sceneStart, int startOffsetMs, int assemblyOffsetMs, int endOffsetMs, int layoutIndex) {
    sceneStartedAt = sceneStart;
    slotStartMs = startOffsetMs;
    assembleEndMs = max(startOffsetMs + 1, assemblyOffsetMs);
    slotEndMs = max(assembleEndMs + 1, endOffsetMs);
    layoutSentence(sentence, layoutIndex);
    scheduleWordFlights();
  }

  void layoutSentence(String sentence, int layoutIndex) {
    textFont(myFont, fontSize);
    float boxW = width * random(0.34f, 0.50f);
    
    int column = layoutIndex % 2;
    int row = (layoutIndex / 2) % 3;
    
    float x = column == 0 ? width * 0.08f : width * 0.52f;
    x += random(-width * 0.025f, width * 0.025f);
    float y = height * (0.18f + row * 0.25f) + random(-20, 20);
    
    if (x > width * 0.35f && y > height * 0.3f) {
      x = x - (width * 0.50f); 
      
      if (x < width * 0.05f) {
        x = width * 0.05f; 
      }
    }
    if (y > height*0.6) {
      y = (height*0.5);
    }
    
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

  void scheduleWordFlights() {
    int assemblyMs = max(1, assembleEndMs - slotStartMs);
    int maxFlightMs = max(1, min(flightBufferMs, assemblyMs));
    int minFlightMs = min(WORD_MIN_FLIGHT_MS, maxFlightMs);
    int wordCount = max(1, words.size());
    
    for (int index = 0; index < words.size(); index++) {
      FlyingWord word = words.get(index);
      float distancePx = PVector.dist(word.startPos, word.target);
      int naturalFlightMs = round((distancePx / WORD_FLIGHT_PX_PER_SECOND) * 1000.0f);
      int flightMs = constrain(naturalFlightMs, minFlightMs, maxFlightMs);
      int earliestArrivalMs = slotStartMs + flightMs;
      int latestArrivalMs = assembleEndMs;
      int arrivalMs = wordCount == 1
        ? latestArrivalMs
        : round(map(index, 0, wordCount - 1, earliestArrivalMs, latestArrivalMs));
      arrivalMs = constrain(arrivalMs, earliestArrivalMs, latestArrivalMs);
      word.scheduleFlight(arrivalMs - flightMs, arrivalMs);
    }
  }

  void update() {
    int elapsed = millis() - sceneStartedAt;
    if (elapsed < slotStartMs) return;
    
    started = true;
    opacity = min(255, opacity + 18);

    for (FlyingWord word : words) {
      word.update(elapsed);
    }

    if (elapsed >= slotEndMs) {
      opacity = max(0, opacity - 21);
    }
  }

  void draw(Atmosphere atmosphere) {
    if (!started) return;
    textFont(myFont, fontSize);
    for (FlyingWord word : words) {
      word.opacity = opacity;
      if (word.active) word.displayBase(atmosphere.textColor, atmosphere.glowColor);
    }
  }

  boolean isInvisibleAndFinished() {
    return millis() - sceneStartedAt >= slotEndMs && opacity <= 1;
  }
}
