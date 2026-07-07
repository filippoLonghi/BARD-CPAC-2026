final float MIN_LATE_SCENE_DURATION_S = 2.0f;

class StoryDirector {
  /* classe "regista" che gestisce la playlist, 
  cambi scena, tempi e sa quando è in play
  */
  
  ArrayList<Segmento> playlist = new ArrayList<Segmento>();

  float slideDuration = 10.0;
  boolean isPlaying = false;
  boolean streamingMode = false;
  boolean streamFinished = false;
  
  boolean isOutro = false;
  int outroStartTime = 0;

  int currentSegmentIndex = -1;
  int lastSegmentTime = 0;
  int performanceStartTime = 0;
  int currentSegmentEarliestEndMs = 0;

  int pendingImageReloadId = -1;
  int primedSegmentId = -1;

  StoryDirector() {}

  // azzera tutto (usato quando riceve il segnale di reset)
  void reset() {
    processingAudioPlayer.close();
    playlist.clear();
    currentSegmentIndex = -1;
    isPlaying = false;
    isOutro = false;
    performanceStartTime = 0;
    streamingMode = false;
    streamFinished = false;
    pendingImageReloadId = -1;
    primedSegmentId = -1;
    outroStartTime = 0;
    currentSegmentEarliestEndMs = 0;
  }

  void addSegment(Segmento segment) {
    playlist.add(segment);
  }

  Segmento findSegment(int segmentId) {
    for (Segmento segment : playlist) {
      if (segment.id == segmentId) return segment;
    }
    return null;
  }

  float performanceElapsedSeconds() {
    if (!isPlaying) return 0;
    return max(0, (millis() - performanceStartTime) / 1000.0f);
  }

  // carica in memoria i testi, le atmosfere e le immagini della nuova scena
  void loadNextSegment() {
    if (playlist.size() == 0) return;

    int nextIndex = currentSegmentIndex + 1;
    if (nextIndex >= playlist.size()) return;

    currentSegmentIndex = nextIndex;
    Segmento segment = playlist.get(currentSegmentIndex);

    println(">>> SEGMENT " + currentSegmentIndex + " | mood: " + segment.categoria);
    println(">>> TESTO: " + segment.testo);

    // manda gli ordini ai vari "reparti" tecnici
    moodManager.setMood(segment.categoria);

    float elapsedSeconds = performanceElapsedSeconds();
    slideDuration = max(MIN_LATE_SCENE_DURATION_S, segment.endSeconds - elapsedSeconds);

    wordsystem.beginScene(segment.testo, slideDuration);
    currentSegmentEarliestEndMs = millis() + round(slideDuration * 1000.0f);

    if (segment.id != primedSegmentId) {
      loadSegmentImages(segment);
    }
    primedSegmentId = -1;
    lastSegmentTime = millis();
  }
  
  // funzione per la schermata finale
  void startOutro() {
    println(">>> OUTRO: The End");
    isOutro = true;
    outroStartTime = millis();
    
    // cancella tutte le particelle delle immagini e i testi rimasti
    imgSystems.clear();
    wordsystem = new WordsSystem();
    
    // riporta l'atmosfera al blu sereno iniziale in modo fluido
    moodManager.setMood("CALM"); 
  }

  // controlla l'orologio e decide se è ora di far entrare la prossima scena
  void advanceTimeline() {
    if (isOutro) {
      if (millis() - outroStartTime > 5000) { // 5000 sono i millisecondi della scritta "the End"
        reset(); 
        wordsystem = new WordsSystem();
        imgSystems.clear();
      }
      return;
    }
    
    int nextIndex = currentSegmentIndex + 1;
    if (nextIndex < playlist.size()) {
      if (streamingMode && currentSegmentIndex >= 0 && millis() < currentSegmentEarliestEndMs) return;
      Segmento nextSegment = playlist.get(nextIndex);
      if (performanceElapsedSeconds() + 0.02f < nextSegment.startSeconds) return; 
      loadNextSegment();
    }
    
    // se le scene sono finite ed è finito il tempo per mandare le cose
    else if (streamFinished && currentSegmentIndex >= 0 && currentSegmentIndex == playlist.size() - 1) {
      Segmento lastSegment = playlist.get(currentSegmentIndex);
      // aspetta 4 secondi dopo la fine dell'ultima scena, poi lancia "The End"
      if (performanceElapsedSeconds() >= lastSegment.endSeconds + 4.0f) { 
        startOutro();
      }
    }
  }

  // Iiserisce al volo le immagini che ci mettono tanto a caricare 
  void applyPendingImageReload() {
    if (pendingImageReloadId < 0) return;
    Segmento segment = findSegment(pendingImageReloadId);
    pendingImageReloadId = -1;
    if (segment != null && currentSegmentIndex >= 0 && playlist.get(currentSegmentIndex).id == segment.id) {
      loadSegmentImages(segment);
    }
  }

  void startShow() {
    if (playlist.size() > 0) {
      println(">>> START SHOW");
      processingAudioPlayer.playFromStart();
      isPlaying = true;
      isOutro = false;
      performanceStartTime = millis();
      currentSegmentIndex = -1;
      lastSegmentTime = millis();
      loadNextSegment();
    }
  }
}
