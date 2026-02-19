class Mragent < Formula
  desc "Lightweight, open-source AI Agent powered by free APIs"
  homepage "https://github.com/bonzainsights/MRAgent"
  url "https://github.com/bonzainsights/MRAgent/archive/refs/heads/main.tar.gz"
  version "0.1.0"
  sha256 "SKIP" # We'll use HEAD mostly, users should use --HEAD

  depends_on "python@3.11"
  depends_on "portaudio" # For sounddevice
  depends_on "ffmpeg"    # For audio processing

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/mragent", "--help"
  end
end
