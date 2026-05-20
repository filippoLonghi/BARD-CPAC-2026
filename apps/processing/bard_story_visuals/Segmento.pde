class Segmento {
  String categoria;
  String testo;
  String imagePath;  // opzionale: path immagine associata al segmento

  Segmento(String c, String t) {
    categoria = c;
    testo     = t;
    imagePath = null;
  }

  Segmento(String c, String t, String img) {
    categoria = c;
    testo     = t;
    imagePath = img;
  }
}
