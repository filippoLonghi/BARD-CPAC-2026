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
