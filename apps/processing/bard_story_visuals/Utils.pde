// --------------- UTILS ---------------
// funzioni strumento per adattamenti, decodifiche e altre cose

/* funzione per l' adattamento dell'area per le immagini 
in base alla dimensione dello schermo che abbiamo: */
void calcImageRect() {
  imgX = width * imageMarginX;
  imgY = height * imageMarginTop;
  imgW = width * (1.0 - 2 * imageMarginX);
  imgH = height * imageAreaRatio;
}


/* funzione per decodificare il testo da UTF-8 
per fare funzionare le lettere accentate */
String normalizeDisplayText(String value) {
  if (value == null) return "";
  String decoded = value;
  try {
    decoded = URLDecoder.decode(value, "UTF-8"); //decodifica che serve ad avere le lettere accentate
  } catch (Exception e) {
    println(">>> Errore di decodifica sul testo: " + value);
  }
  String normalized = Normalizer.normalize(decoded, Normalizer.Form.NFC); // standardizza
  normalized = normalized.replace('\u2018', '\'').replace('\u2019', '\'');  // risolve gli apici strani
  normalized = normalized.replace('\u201C', '"').replace('\u201D', '"');
  
  return normalized;
}


/* inseriamo esplicitamente tutte le lettere italiane e le accentate 
per avere la certezza che processing le proietti */
char[] buildItalianCharset() {
  String chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789àèéìòùÀÈÉÌÒÙ .,;:'\"!?()[]{}-_+*/=<>&#%@\\|^~";
  return chars.toCharArray();
}


/* BACCHETTA MAGICA (Flood Fill) per rimuovere sfondi e cornici */

boolean[] calculateFloodFillMask(PImage img) {
  boolean[] bgMask = new boolean[img.width * img.height];
  
  // Usiamo un array nativo invece di ArrayList per una velocità estrema!
  int[] queue = new int[img.width * img.height];
  int head = 0;
  int tail = 0;
  
  // 1. Cerchiamo sui bordi dell'immagine.
  for (int y = 0; y < img.height; y++) {
    for (int x = 0; x < img.width; x++) {
      if (x == 0 || x == img.width - 1 || y == 0 || y == img.height - 1) {
        int idx = x + y * img.width;
        float b = brightness(img.pixels[idx]);
        
        // Tolleranza: prendiamo il nero profondo e il bianco puro
        if (b < 20 || b > 230) {
          bgMask[idx] = true;
          queue[tail++] = idx;
        }
      }
    }
  }
  
  // 2. Espansione a macchia d'olio
  int[] dx = {-1, 1, 0, 0};
  int[] dy = {0, 0, -1, 1};
  
  while (head < tail) {
    int idx = queue[head++];
    int cx = idx % img.width;
    int cy = idx / img.width;
    
    for (int i = 0; i < 4; i++) {
      int nx = cx + dx[i];
      int ny = cy + dy[i];
      
      if (nx >= 0 && nx < img.width && ny >= 0 && ny < img.height) {
        int nIdx = nx + ny * img.width;
        if (!bgMask[nIdx]) {
          float b = brightness(img.pixels[nIdx]);
          // Tolleranza di compressione: mangia solo colori simili a bordi o sfondo vuoto
          if (b < 20 || b > 230) { 
            bgMask[nIdx] = true;
            queue[tail++] = nIdx;
          }
        }
      }
    }
  }
  
  return bgMask;
}


boolean hasTransparentPixels(PImage img) {
  img.loadPixels();
  for (int i = 0; i < img.pixels.length; i++) {
    if (alpha(img.pixels[i]) < 250) return true;
  }
  return false;
}


// TAGLIERINA GEOMETRICA PER CORNICI AI BORDI
PImage autoCropFrames(PImage img) {
  img.loadPixels();
  int top = 0;
  int bottom = img.height - 1;
  int left = 0;
  int right = img.width - 1;

  for (int y = 0; y < img.height; y++) {
    if (!isRowBackground(img, y)) {
      top = y;
      break;
    }
  }
  for (int y = img.height - 1; y >= top; y--) {
    if (!isRowBackground(img, y)) {
      bottom = y;
      break;
    }
  }
  for (int x = 0; x < img.width; x++) {
    if (!isColBackground(img, x, top, bottom)) {
      left = x;
      break;
    }
  }
  for (int x = img.width - 1; x >= left; x--) {
    if (!isColBackground(img, x, top, bottom)) {
      right = x;
      break;
    }
  }

  int newW = right - left + 1;
  int newH = bottom - top + 1;

  if (newW <= 10 || newH <= 10) return img;
  if (newW == img.width && newH == img.height) return img;

  return img.get(left, top, newW, newH);
}

// --- Funzioni assistenti per controllare righe e colonne ---
boolean isRowBackground(PImage img, int y) {
  int bgCount = 0;
  for (int x = 0; x < img.width; x++) {
    float b = brightness(img.pixels[x + y * img.width]);
    if (b < 20 || b > 230) bgCount++;
  }
  // Se il 95% della riga è nero profondo o bianco puro, è una cornice!
  return bgCount > img.width * 0.95;
}

boolean isColBackground(PImage img, int x, int top, int bottom) {
  int bgCount = 0;
  int h = bottom - top + 1;
  for (int y = top; y <= bottom; y++) {
    float b = brightness(img.pixels[x + y * img.width]);
    if (b < 20 || b > 230) bgCount++;
  }
  // Se il 95% della colonna è nero profondo o bianco puro, è una cornice!
  return bgCount > h * 0.95;
}



// funzione per disegnare il titolo con animazione macchina da scrivere
void drawIntroScreen(String introTitle, PFont fontT, String introSubtitle, PFont fontS) {
  int totalChars = introTitle.length() + introSubtitle.length();
  int now = millis();
  
  int typingSpeed = 90;  // Millisecondi di attesa tra una lettera e l'altra
  int waitTime = 2000;   // Pausa a fine frase (2000 ms = 2 secondi)
  
  if (introWaiting) {
    if (now - introLastTime > waitTime) {
      introWaiting = false;
      introCharIndex = 0; // Tempo scaduto: resetta tutto e ricomincia!
      introLastTime = now;
    }
  } else {
    if (now - introLastTime > typingSpeed) {
      introCharIndex++;
      if (introCharIndex >= totalChars) {
        introCharIndex = totalChars;
        introWaiting = true; // Ha finito di scrivere, inizia i 2 secondi di attesa
      }
      introLastTime = now;
    }
  }
  
  textAlign(CENTER, CENTER);
  fill(255); // Colore del testo (bianco)
  
  // titolo
  int titleChars = min(introCharIndex, introTitle.length());
  String currentTitle = introTitle.substring(0, titleChars);
  
  textFont(fontT);
  if (introSubtitle == "") {
    text(currentTitle, width / 2, height / 2);
  } else   text(currentTitle, width / 2, height / 2 - 40);
  
  // finito il titolo, sottotiolo
  int subChars = max(0, introCharIndex - introTitle.length());
  String currentSubtitle = introSubtitle.substring(0, subChars);
  
  textFont(fontS);
  text(currentSubtitle, width / 2, height / 2 + 40);
}
