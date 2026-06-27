class ImageLayer {
  int layerIndex;
  String role;
  String path;

  ImageLayer(int idx, String r, String p) {
    layerIndex = idx;
    role = r;
    path = p;
  }
}

class MoodCue {
  String mood;
  float startSeconds;
  float endSeconds;

  MoodCue(String moodValue, float startValue, float endValue) {
    mood = moodValue;
    startSeconds = startValue;
    endSeconds = endValue;
  }
}

class Segmento {
  int id;
  String categoria;
  String testo;
  String displayText;
  float startSeconds;
  float endSeconds;
  ArrayList<String> keywords = new ArrayList<String>();
  ArrayList<ImageLayer> imageLayers = new ArrayList<ImageLayer>();
  ArrayList<MoodCue> moodCues = new ArrayList<MoodCue>();

  Segmento(int segmentId, String mood, String textValue, String displayValue, float startValue, float endValue) {
    id = segmentId;
    categoria = mood;
    testo = textValue;
    displayText = displayValue;
    startSeconds = startValue;
    endSeconds = endValue;
  }

  void addImage(int layerIndex, String role, String path) {
    for (int i = 0; i < imageLayers.size(); i++) {
      if (imageLayers.get(i).layerIndex == layerIndex) {
        imageLayers.set(i, new ImageLayer(layerIndex, role, path));
        return;
      }
    }
    imageLayers.add(new ImageLayer(layerIndex, role, path));
  }

  void addMoodCue(String mood, float startValue, float endValue) {
    if (endValue <= startValue) return;
    moodCues.add(new MoodCue(mood, startValue, endValue));
  }

  int imageCount() {
    return imageLayers.size();
  }

  float durationSeconds() {
    return max(0.1f, endSeconds - startSeconds);
  }

  String imagePathAt(int position) {
    if (position < 0 || position >= imageLayers.size()) return null;
    int wantedIndex = position;
    for (ImageLayer layer : imageLayers) {
      if (layer.layerIndex == wantedIndex) return layer.path;
    }
    return imageLayers.get(position).path;
  }

  ImageLayer imageLayerAt(int position) {
    if (position < 0 || position >= imageLayers.size()) return null;
    for (ImageLayer layer : imageLayers) {
      if (layer.layerIndex == position) return layer;
    }
    return imageLayers.get(position);
  }
}
