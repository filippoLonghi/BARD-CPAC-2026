class WordsSystem{

  final int STATE_WRITING         = 0;
  final int STATE_WAITING_ARRIVAL = 1;
  final int STATE_READING         = 2;
  
  int   currentState      = STATE_WRITING;
  int   currentWordIndex  = 0;
  int   lastWordSpawnTime = 0;
  int   wordSpawnRate     = 110; // tempo tra l'attivazione di una parola e l'altra
  
  ArrayList<FlyingWord> wordsObjects = new ArrayList<FlyingWord>();
  ArrayList<ArrayList<FlyingWord>> pages;
  
  
  void calculatePages() {
    textSize(fontSize);
    pages = new ArrayList<ArrayList<FlyingWord>>();
  
    float textZoneY = imgY + imgH + textAreaPad + fontSize;
    float textZoneX = imgX;
    float textZoneW = imgW;
  
    String[] rawWords = split(fullText, ' ');
    float x = textZoneX;
    float y = textZoneY;
    ArrayList<FlyingWord> currentPage = new ArrayList<FlyingWord>();
  
    for (String str : rawWords) {
      float w = textWidth(str + " ");
      if (x + w > textZoneX + textZoneW) {
        x  = textZoneX;
        y += leading;
      }
      currentPage.add(new FlyingWord(str, x, y, 0));
      x += w;
    }
  
    if (currentPage.size() > 0) pages.add(currentPage);
  }
  
  
  void loadPage(int index) { 
    if (pages != null && pages.size() > 0) {
      wordsObjects     = pages.get(index);
      currentWordIndex = 0;
      currentState     = STATE_WRITING;
      lastWordSpawnTime = millis();
    } else {
      wordsObjects.clear();
    }
  }
  
  void updateWordLogic() {
    int now = millis();
    if (currentState == STATE_WRITING) {
      if (now - lastWordSpawnTime > wordSpawnRate && currentWordIndex < wordsObjects.size()) {
        wordsObjects.get(currentWordIndex).active = true;
        lastWordSpawnTime = now;
        currentWordIndex++;
        if (currentWordIndex >= wordsObjects.size()) currentState = STATE_WAITING_ARRIVAL;
      }
    } else if (currentState == STATE_WAITING_ARRIVAL) {
      if (wordsObjects.size() == 0) {
        currentState = STATE_READING;
      } else if (wordsObjects.get(wordsObjects.size() - 1).locked) {
        currentState = STATE_READING;
        for (FlyingWord w : wordsObjects) w.targetGlow = 255;
      }
    }
  }
  
  void drawWords(Atmosphere currentVals) {
    blendMode(BLEND);
    for (FlyingWord w : wordsObjects) {
      if (w.active) { w.update(); w.displayBase(currentVals.textColor, currentVals.glowColor); }
    }
    blendMode(ADD);
    for (FlyingWord w : wordsObjects) {
      if (w.active && w.currentGlow > 1) w.displayGlowingOnly(currentVals.glowColor);
    }
    blendMode(BLEND);
  }
  

 }
