import java.util.HashMap;
import java.text.Normalizer;
import oscP5.*;
import netP5.*;

OscP5 oscP5;
int port = 5005;
NetAddress pythonVoiceLocation;
NetAddress pythonReadyLocation;

ArrayList<Segmento> playlist = new ArrayList<Segmento>();

float slideDuration = 10.0;
boolean isPlaying = false;
boolean streamingMode = false;
boolean streamFinished = false;
int currentSegmentIndex = -1;
int lastSegmentTime = 0;
int performanceStartTime = 0;

float imageAreaRatio = 0.55;
float imageMarginX = 0.2;
float imageMarginTop = 0.13;
float textAreaPad = 32;

int fontSize = 20;
float leading = fontSize * 1.45;
PFont myFont;
String fullText = "";

WordsSystem wordsystem = new WordsSystem();
ArrayList<BgParticle> bgParticles = new ArrayList<BgParticle>();
MoodManager moodManager;
Nebula nebula;
ArrayList<ImageParticleSystem> imgSystems = new ArrayList<ImageParticleSystem>();
int pendingImageReloadId = -1;
int primedSegmentId = -1;

float imgX, imgY, imgW, imgH;

void setup() {
  fullScreen(P2D);

  oscP5 = new OscP5(this, port);
  pythonVoiceLocation = new NetAddress("127.0.0.1", 5006);
  pythonReadyLocation = new NetAddress("127.0.0.1", 5007);

  myFont = createFont("Arial", fontSize, true, buildDisplayCharset());
  textFont(myFont);
  textSize(fontSize);
  textAlign(LEFT, CENTER);

  nebula = new Nebula();
  moodManager = new MoodManager("CALM");

  Atmosphere currentVals = moodManager.getCurrentVals();
  for (int i = 0; i < (int)currentVals.particleCount; i++) {
    bgParticles.add(new BgParticle());
  }

  calcImageRect();
}

char[] buildDisplayCharset() {
  // Basic Latin, Latin-1, and Latin Extended cover the configured European story languages.
  char[] charset = new char[992];
  for (int index = 0; index < charset.length; index++) {
    charset[index] = (char)(32 + index);
  }
  return charset;
}

void draw() {
  moodManager.update();
  Atmosphere currentVals = moodManager.getCurrentVals();

  int targetCount = (int)currentVals.particleCount;
  while (bgParticles.size() < targetCount) bgParticles.add(new BgParticle());
  while (bgParticles.size() > targetCount) bgParticles.remove(0);

  background(currentVals.bgColor);
  nebula.draw(currentVals.nebulaColor, currentVals.nebulaAlphaMax, currentVals.nebulaSpeed);

  for (BgParticle particle : bgParticles) {
    particle.update(currentVals.particleSpeedY, currentVals.chaos);
    particle.display(currentVals.particleColor);
  }

  if (!isPlaying) {
    fill(255, 220);
    textAlign(CENTER, CENTER);
    textSize(fontSize + 22);
    text("BARD", width / 2.0, height / 2.0 - 36);
    textSize(fontSize - 8);
    text("I'll tell you a story...", width / 2.0, height / 2.0 + 42);
    textAlign(LEFT, CENTER);
    return;
  }

  advanceTimeline();
  applyPendingImageReload();

  updateCurrentSegmentImage(currentVals);
  wordsystem.updateWordLogic();
  wordsystem.drawWords(currentVals);
}

void calcImageRect() {
  imgX = width * imageMarginX;
  imgY = height * imageMarginTop;
  imgW = width * (1.0 - 2 * imageMarginX);
  imgH = height * imageAreaRatio;
}

void loadNextSegment() {
  if (playlist.size() == 0) return;

  int nextIndex = currentSegmentIndex + 1;
  if (nextIndex >= playlist.size()) {
    return;
  }
  currentSegmentIndex = nextIndex;

  Segmento segment = playlist.get(currentSegmentIndex);
  println(">>> SEGMENT " + currentSegmentIndex + " | mood: " + segment.categoria);
  println(">>> TEXT: " + segment.testo);

  moodManager.setMood(segment.categoria);
  float elapsedSeconds = performanceElapsedSeconds();
  slideDuration = max(0.5f, segment.endSeconds - elapsedSeconds);
  wordsystem.beginScene(segment.testo, slideDuration);
  if (segment.id != primedSegmentId) loadSegmentImages(segment);
  primedSegmentId = -1;

  lastSegmentTime = millis();
}

float performanceElapsedSeconds() {
  if (!isPlaying) return 0;
  return max(0, (millis() - performanceStartTime) / 1000.0f);
}

void advanceTimeline() {
  int nextIndex = currentSegmentIndex + 1;
  while (nextIndex < playlist.size()) {
    Segmento nextSegment = playlist.get(nextIndex);
    if (performanceElapsedSeconds() + 0.02f < nextSegment.startSeconds) return;
    loadNextSegment();
    nextIndex = currentSegmentIndex + 1;
  }
}

void updateCurrentSegmentImage(Atmosphere currentVals) {
  if (!isPlaying || currentSegmentIndex < 0 || currentSegmentIndex >= playlist.size()) return;

  for (ImageParticleSystem system : imgSystems) {
    system.updateAndDisplay(currentVals.chaos * 2);
  }
}

void loadSegmentImages(Segmento segment) {
  imgSystems.clear();
  float sceneDuration = segment.durationSeconds();
  float firstReveal = random(0.02f, 0.10f);
  float secondReveal = random(0.24f, 0.44f);
  float thirdReveal = random(0.55f, 0.78f);
  for (int position = 0; position < segment.imageCount(); position++) {
    ImageLayer layer = segment.imageLayerAt(position);
    if (layer == null || layer.path == null || layer.path.length() == 0) continue;

    float rx = 0;
    float ry = 0;
    float rw = width;
    float rh = height;
    if (layer.role.equals("subject")) {
      rw = width * random(0.30f, 0.42f);
      rh = height * random(0.42f, 0.60f);
      rx = random(1) < 0.5f ? width * 0.04f : width - rw - width * 0.04f;
      ry = random(height * 0.16f, height - rh - height * 0.08f);
    } else if (layer.role.equals("symbol")) {
      rw = width * random(0.16f, 0.25f);
      rh = height * random(0.18f, 0.30f);
      rx = random(width * 0.08f, width - rw - width * 0.08f);
      ry = random(height * 0.12f, height - rh - height * 0.12f);
    }

    ImageParticleSystem system = new ImageParticleSystem();
    system.loadAndConvert(layer.path, rx, ry, rw, rh, layer.role);
    if (position == 0) system.revealAtSeconds = segment.startSeconds + sceneDuration * firstReveal;
    else if (position == 1) system.revealAtSeconds = segment.startSeconds + sceneDuration * secondReveal;
    else system.revealAtSeconds = segment.startSeconds + sceneDuration * thirdReveal;
    imgSystems.add(system);
  }
}

void applyPendingImageReload() {
  if (pendingImageReloadId < 0) return;
  Segmento segment = findSegment(pendingImageReloadId);
  pendingImageReloadId = -1;
  if (segment != null && currentSegmentIndex >= 0 && playlist.get(currentSegmentIndex).id == segment.id) {
    loadSegmentImages(segment);
  }
}

String normalizeDisplayText(String value) {
  if (value == null) return "";
  String normalized = Normalizer.normalize(value, Normalizer.Form.NFC);
  normalized = normalized.replace('\u2018', '\'').replace('\u2019', '\'');
  normalized = normalized.replace('\u201C', '"').replace('\u201D', '"');
  return normalized;
}

void oscEvent(OscMessage message) {
  println("OSC: " + message.addrPattern());

  if (message.checkAddrPattern("/reset")) {
    playlist.clear();
    currentSegmentIndex = -1;
    isPlaying = false;
    performanceStartTime = 0;
    streamingMode = false;
    streamFinished = false;
    fullText = "";
    imgSystems.clear();
    pendingImageReloadId = -1;
    primedSegmentId = -1;
    wordsystem = new WordsSystem();
    println(">>> Playlist reset");
    return;
  }

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

  if (message.checkAddrPattern("/prime")) {
    int readyPort = 5007;
    if (message.checkTypetag("i")) readyPort = message.get(0).intValue();
    if (playlist.size() == 0) {
      println(">>> Cannot prime: no scene received");
      return;
    }
    pythonReadyLocation = new NetAddress("127.0.0.1", readyPort);
    Segmento firstSegment = playlist.get(0);
    moodManager.setMood(firstSegment.categoria);
    loadSegmentImages(firstSegment);
    primedSegmentId = firstSegment.id;
    OscMessage primedMessage = new OscMessage("/primed");
    primedMessage.add(primedSegmentId);
    oscP5.send(primedMessage, pythonReadyLocation);
    println(">>> PRIMED scene " + primedSegmentId);
    return;
  }

  if (message.checkAddrPattern("/config/duration")) {
    if (message.checkTypetag("f")) slideDuration = message.get(0).floatValue();
    else if (message.checkTypetag("i")) slideDuration = message.get(0).intValue();
    println(">>> Slide duration: " + slideDuration);
    return;
  }

  if (message.checkAddrPattern("/config/streaming")) {
    if (message.checkTypetag("i")) streamingMode = message.get(0).intValue() != 0;
    println(">>> Streaming mode: " + streamingMode);
    return;
  }

  if (message.checkAddrPattern("/segment")) {
    int segmentId;
    String mood;
    String textValue;
    String displayValue;
    float startValue = playlist.size() * slideDuration;
    float endValue = startValue + slideDuration;

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
      segmentId = playlist.size() + 1;
      mood = message.get(0).stringValue();
      textValue = normalizeDisplayText(message.get(1).stringValue());
      displayValue = textValue;
    } else {
      println(">>> Unsupported /segment typetag: " + message.typetag());
      return;
    }

    playlist.add(new Segmento(segmentId, mood, textValue, displayValue, startValue, endValue));
    println(">>> Received segment " + segmentId + ": " + textValue);
    return;
  }

  if (message.checkAddrPattern("/keywords")) {
    int segmentId = message.get(0).intValue();
    Segmento segment = findSegment(segmentId);
    if (segment != null) {
      segment.keywords.clear();
      for (int i = 1; i < message.arguments().length; i++) {
        segment.keywords.add(message.get(i).stringValue());
      }
    }
    return;
  }

  if (message.checkAddrPattern("/image")) {
    int segmentId = message.get(0).intValue();
    int layerIndex = message.get(1).intValue();
    String role = message.get(2).stringValue();
    String path = message.get(3).stringValue();

    Segmento segment = findSegment(segmentId);
    if (segment != null) {
      segment.addImage(layerIndex, role, path);
      println(">>> Received image for segment " + segmentId + ": " + role + " -> " + path);
      if (isPlaying && currentSegmentIndex >= 0 && playlist.get(currentSegmentIndex).id == segmentId) {
        pendingImageReloadId = segmentId;
      }
    } else {
      println(">>> Ignored image, segment not found: " + segmentId);
    }
    return;
  }

  if (message.checkAddrPattern("/start")) {
    if (playlist.size() > 0) {
      println(">>> START");
      isPlaying = true;
      performanceStartTime = millis();
      currentSegmentIndex = -1;
      lastSegmentTime = millis();
      loadNextSegment();
    }
    return;
  }

  if (message.checkAddrPattern("/finish")) {
    streamFinished = true;
    println(">>> Stream finished; holding final segment");
    return;
  }
}

Segmento findSegment(int segmentId) {
  for (Segmento segment : playlist) {
    if (segment.id == segmentId) return segment;
  }
  return null;
}
