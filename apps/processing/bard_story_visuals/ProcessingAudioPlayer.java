import java.io.File;
import javax.sound.sampled.AudioInputStream;
import javax.sound.sampled.AudioSystem;
import javax.sound.sampled.Clip;

class ProcessingAudioPlayer {
  private Clip clip;

  void load(String path) throws Exception {
    close();
    AudioInputStream input = AudioSystem.getAudioInputStream(new File(path));
    try {
      clip = AudioSystem.getClip();
      clip.open(input);
    } finally {
      input.close();
    }
  }

  void playFromStart() {
    if (clip == null) return;
    clip.stop();
    clip.setFramePosition(0);
    clip.start();
  }

  void close() {
    if (clip == null) return;
    clip.stop();
    clip.close();
    clip = null;
  }
}
