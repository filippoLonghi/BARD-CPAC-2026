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
