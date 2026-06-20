class OscHandler {
  /* classe per la gestione dei messaggi OSC che arrivano e settano cose diverse.
     setta tutti i parametri e il testo delle variabili nel main */
  
  void handleMessage(OscMessage message) {
    
    println("OSC: " + message.addrPattern());

    // reset della storia e dei parametri 
    if (message.checkAddrPattern("/reset")) {
      director.reset();
      wordsystem = new WordsSystem();
      imgSystems.clear();
      println(">>> Playlist reset");
      return;
    }
    
    // messaggio per fare partire l'audio 
    if (message.checkAddrPattern("/audio")) {
      if (message.checkTypetag("s")) {
        processingAudioPath = message.get(0).stringValue();
        println(">>> Audio path: " + processingAudioPath);
      }
      return;
    }
    // handshake in cui risponde a python che è pronto a ricevere
    if (message.checkAddrPattern("/prepare")) {
      int readyPort = 5007;
      if (message.checkTypetag("i")) readyPort = message.get(0).intValue();
      pythonReadyLocation = new NetAddress("127.0.0.1", readyPort);
      OscMessage readyMessage = new OscMessage("/ready");
      readyMessage.add(1);
      oscP5.send(readyMessage, pythonReadyLocation);
      println(">>> READY");
      return;
    }
    
    // preparazione prima scena per cominciare
    if (message.checkAddrPattern("/prime")) {
      int readyPort = 5007;
      if (message.checkTypetag("i")) readyPort = message.get(0).intValue();
      if (director.playlist.size() == 0) {
        println(">>> Cannot prime: no scene received");
        return;
      }
      pythonReadyLocation = new NetAddress("127.0.0.1", readyPort);
      Segmento firstSegment = director.playlist.get(0);
      
      if (processingAudioPath.length() > 0) {
        try {
          processingAudioPlayer.load(processingAudioPath);
        } catch (Exception error) {
          println(">>> Cannot load Processing audio: " + error.getMessage());
          return;
        }
      }
      moodManager.setMood(firstSegment.categoria);
      loadSegmentImages(firstSegment);
      director.primedSegmentId = firstSegment.id;
      OscMessage primedMessage = new OscMessage("/primed");
      primedMessage.add(director.primedSegmentId);
      oscP5.send(primedMessage, pythonReadyLocation);
      println(">>> PRIMED scene " + director.primedSegmentId);
      return;
    }
    
    // configurazioni 
    if (message.checkAddrPattern("/config/duration")) {
      if (message.checkTypetag("f")) director.slideDuration = message.get(0).floatValue();
      else if (message.checkTypetag("i")) director.slideDuration = message.get(0).intValue();
      println(">>> Slide duration: " + director.slideDuration);
      return;
    }

    if (message.checkAddrPattern("/config/streaming")) {
      if (message.checkTypetag("i")) director.streamingMode = message.get(0).intValue() != 0;
      println(">>> Streaming mode: " + director.streamingMode);
      return;
    }

    // recezione di tutto il contenuto del segmento, mood testo e durata
    // prepara la playlist di segmenti 
    if (message.checkAddrPattern("/segment")) {
      int segmentId;
      String mood;
      String textValue;
      String displayValue;
      float startValue = director.playlist.size() * director.slideDuration;
      float endValue = startValue + director.slideDuration;

      if (message.checkTypetag("issff")) {
        segmentId = message.get(0).intValue();
        mood = message.get(1).stringValue();
        textValue = normalizeDisplayText(message.get(2).stringValue());
        displayValue = textValue;
        startValue = message.get(3).floatValue();
        endValue = message.get(4).floatValue();
      } else if (message.checkTypetag("isss")) {
        segmentId = message.get(0).intValue();
        mood = message.get(1).stringValue();
        textValue = normalizeDisplayText(message.get(2).stringValue());
        displayValue = normalizeDisplayText(message.get(3).stringValue());
      } else if (message.checkTypetag("iss")) {
        segmentId = message.get(0).intValue();
        mood = message.get(1).stringValue();
        textValue = normalizeDisplayText(message.get(2).stringValue());
        displayValue = textValue;
      } else if (message.checkTypetag("ss")) {
        segmentId = director.playlist.size() + 1;
        mood = message.get(0).stringValue();
        textValue = normalizeDisplayText(message.get(1).stringValue());
        displayValue = textValue;
      } else {
        println(">>> Unsupported /segment typetag: " + message.typetag());
        return;
      }

      director.addSegment(new Segmento(segmentId, mood, textValue, displayValue, startValue, endValue));
      println(">>> Received segment " + segmentId + ": " + textValue);
      return;
    }
  
    // recezione keywords del segmento di testo 
    if (message.checkAddrPattern("/keywords")) {
      int segmentId = message.get(0).intValue();
      Segmento segment = director.findSegment(segmentId);
      if (segment != null) {
        segment.keywords.clear();
        for (int i = 1; i < message.arguments().length; i++) {
          segment.keywords.add(message.get(i).stringValue());
        }
      }
      return;
    }

    // recezione immagine generata per il segmento 
    if (message.checkAddrPattern("/image")) {
      int segmentId = message.get(0).intValue();
      int layerIndex = message.get(1).intValue();
      String role = message.get(2).stringValue();
      String path = message.get(3).stringValue();

      Segmento segment = director.findSegment(segmentId);
      if (segment != null) {
        segment.addImage(layerIndex, role, path);
        println(">>> Received image for segment " + segmentId + ": " + role + " -> " + path);
        if (director.isPlaying && director.currentSegmentIndex >= 0 && director.playlist.get(director.currentSegmentIndex).id == segmentId) {
          director.pendingImageReloadId = segmentId;
        }
      } else {
        println(">>> Ignored image, segment not found: " + segmentId);
      }
      return;
    }

    // fa partire tutto, e il tempo
    if (message.checkAddrPattern("/start")) {
      director.startShow();
      return;
    }
    
    // python comunica che ha finito di mandare
    if (message.checkAddrPattern("/finish")) {
      director.streamFinished = true;
      println(">>> Stream finished; holding final segment");
      return;
    }
  }
}
