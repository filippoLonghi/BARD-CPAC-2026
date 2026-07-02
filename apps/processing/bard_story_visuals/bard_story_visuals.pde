import java.util.HashMap;
import java.text.Normalizer;
import oscP5.*;
import netP5.*;
import java.net.URLDecoder; // decoder per i caratteri accentati 

// variabili di rete
OscP5 oscP5;
int port = 5005;
NetAddress pythonVoiceLocation;
NetAddress pythonReadyLocation;

// variabili di schermata immagini
float imageAreaRatio = 0.55;
float imageMarginX = 0.2;
float imageMarginTop = 0.13;
float textAreaPad = 32;

float imgX, imgY, imgW, imgH;

// variabili dei font
float fontPercent = 0.05; //così il font dovrebbe essere sempre della stessa proporzione in altezza 
int fontSize = int(height*fontPercent);
float leading = fontSize * 1.45;
PFont myFont;
PFont myTitle;
String fullText = "";

// variabili per l'animazione della schermata iniziale
int introCharIndex = 0;
int introLastTime = 0;
boolean introWaiting = false;

// oggetti che ci servono
WordsSystem wordsystem = new WordsSystem();
ArrayList<BgParticle> bgParticles = new ArrayList<BgParticle>();
MoodManager moodManager;
Nebula nebula;
HashMap<String, ImageParticleSystem> imgSystems = new HashMap<String, ImageParticleSystem>();

OscHandler oscHandler;
StoryDirector director;

// variabili dell'audoi player
String processingAudioPath = "";
ProcessingAudioPlayer processingAudioPlayer = new ProcessingAudioPlayer();



// ---------- SETUP -------------
void setup() {
  size(600, 400, P2D);
  windowResizable(true);

  oscP5 = new OscP5(this, port);
  pythonVoiceLocation = new NetAddress("127.0.0.1", 5006);
  pythonReadyLocation = new NetAddress("127.0.0.1", 5007);
  
  myFont = createFont("AlteHaasGrotesk", fontSize, true, buildItalianCharset()); //ProcessingSans-Bold AlteHaasGrotesk
  myTitle = createFont("Georgia", fontSize*2.5, true);
  textFont(myFont);
  textSize(fontSize);
  textAlign(LEFT, CENTER);

  nebula = new Nebula();
  moodManager = new MoodManager("CALM");

  oscHandler = new OscHandler();
  director = new StoryDirector();

  Atmosphere currentVals = moodManager.getCurrentVals();
  for (int i = 0; i < (int)currentVals.particleCount; i++) {
    bgParticles.add(new BgParticle());
  }

  calcImageRect();
}


// ---------- DRAW -------------
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

  // testata iniziale prima che parta la storia
  if (!director.isPlaying) {
    fill(255, 220);
    textAlign(CENTER, CENTER);
    drawIntroScreen("BARD", myTitle, "I'll tell you a story...", myFont);
    textAlign(LEFT, CENTER);
    return;
  }
  
  director.advanceTimeline();
  director.applyPendingImageReload();
  
  if (director.isOutro) { //se è finito fa la schermata di fine 
    fill(currentVals.textColor); // Usa il colore di testo armonioso del mood
    textAlign(CENTER, CENTER);
    textFont(myTitle);
    text("The End", width / 2.0, height / 2.0);
    textAlign(LEFT, CENTER);
    textFont(myFont);
  } else { // scorre il tempo e controlla se c'è da cambiare
    updateCurrentSegmentImage(currentVals);
    wordsystem.updateWordLogic();
    wordsystem.drawWords(currentVals);
  }
}


// ------ gestione immagini ------

void updateCurrentSegmentImage(Atmosphere currentVals) {
  if (!director.isPlaying || director.currentSegmentIndex < 0 || director.currentSegmentIndex >= director.playlist.size()) return;
  
  // Disegniamo con un ordine fisso per avere la giusta profondità
  String[] drawOrder = {"background", "subject"};
  
  for (String role : drawOrder) {
    if (imgSystems.containsKey(role)) {
      imgSystems.get(role).updateAndDisplay(currentVals.chaos * 2);
    }
  }
}


void loadSegmentImages(Segmento segment) {
  for (int position = 0; position < segment.imageCount(); position++) {
    ImageLayer layer = segment.imageLayerAt(position);
    if (layer == null || layer.path == null || layer.path.length() == 0) continue;

    String role = layer.role;
    
    // Se è la prima volta che incontriamo questo ruolo, creiamo il suo sciame di particelle
    if (!imgSystems.containsKey(role)) {
      imgSystems.put(role, new ImageParticleSystem());
    }

    // Peschiamo il sistema GIUSTO in base al nome
    ImageParticleSystem system = imgSystems.get(role);

    float rx = 0;
    float ry = 0;
    float rw = width;
    float rh = height;

    if (role.equals("background")) {
      rx = 0;
      ry = 0;
      rw = width;
      rh = height;
    } else if (role.equals("subject")) {
      rw = width * 0.36f;
      rh = height * 0.55f;
      rx = width * 0.58f; 
      ry = height * 0.38f;
    }

    // Le vecchie particelle ricevono le nuove coordinate e i nuovi colori!
    system.loadAndConvert(layer.path, rx, ry, rw, rh, role);
  }
}

// ------------ OSC ------------
void oscEvent(OscMessage message) {
  // gestone delegata alla classe OSC handler 
  if (oscHandler != null) {
    oscHandler.handleMessage(message);
  }
}

// gestione resize della finestra e modifica conseguente del fontSize
void windowResized() {
  fontSize = int(height * fontPercent);
  leading = fontSize * 1.45;
  
  myFont = createFont("AlteHaasGrotesk", fontSize, true, buildItalianCharset());
  myTitle = createFont("Georgia", fontSize * 2.5, true);
  textFont(myFont);
  
  calcImageRect();
}
