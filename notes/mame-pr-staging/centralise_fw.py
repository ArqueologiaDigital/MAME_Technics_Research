"""Centralise the firmware locations the KN7000 driver depends on, and drop the
firmware-site citations that were only provenance."""
import re

p = 'src/mame/matsushita/kn7000.cpp'
s = open(p, encoding='utf-8').read()


def cut(old, new=''):
    global s
    assert old in s, 'MISSING: %r' % old[:76]
    s = s.replace(old, new, 1)


BLOCK = '''namespace {

// Locations inside the running firmware, not hardware registers. The driver has
// to know a few because the machine exposes no other way to reach them: which
// handler an interrupt vector should enter, where the voice records the tone
// generator resolves pitch from live, and the SD transport state behind the
// front-panel lamp. They move between firmware revisions, so they are pinned
// here rather than spelled out at each use.
namespace fw {

// Interrupt entry points. The KN7000 installs two handlers in its self-loaded
// library and splits the levels between them; the KN6000, KN6500, KN2400 and
// KN2600 build a trampoline table instead and send every level to slot 0.
constexpr offs_t KN7000_IRQ_DISPATCH   = 0x4C03DDA0;   // device levels, no stack switch
constexpr offs_t KN7000_IRQ_SCHEDULER  = 0x4C03DE26;   // the level-6 system tick
constexpr offs_t TRAMPOLINE_SLOT0      = 0x90000000;

// Per-slot voice records, 0xB4 stride, 128 slots. Each carries the musical
// pitch the firmware computed, which is what the tone generator plays.
constexpr offs_t KN7000_VOICE_RECORDS  = 0x500AF940;
constexpr offs_t KN6000_VOICE_RECORDS  = 0x5027AF28;
constexpr offs_t KN6500_VOICE_RECORDS  = 0x5027AF1C;

// SD transport state, polled for the PLAY/PAUSE lamp: 1 playing, 2 paused, 0 stopped.
constexpr offs_t SD_AUDIO_PLAY_STATE   = 0x500063E6;
constexpr offs_t SD_SONG_PLAY_STATE    = 0x500063D9;

} // namespace fw

'''
cut('namespace {\n', BLOCK)

# --- code sites ------------------------------------------------------------
cut('\toffs_t  m_tg_recbase   = 0x500AF940;   // library voice-record array (KN6000: 0x502858F8)\n',
    '\toffs_t  m_tg_recbase   = fw::KN7000_VOICE_RECORDS;\n')
cut('\tconst uint8_t sd_aud = prg.read_byte(0x500063e6);\n',
    '\tconst uint8_t sd_aud = prg.read_byte(fw::SD_AUDIO_PLAY_STATE);\n')
cut('\tconst uint8_t sd_snd = prg.read_byte(0x500063d9);\n',
    '\tconst uint8_t sd_snd = prg.read_byte(fw::SD_SONG_PLAY_STATE);\n')
cut('\t\tm_maincpu->set_maskable_vector(level, level == 6 ? 0x4C03DE26 : 0x4C03DDA0);\n',
    '\t\tm_maincpu->set_maskable_vector(level,\n'
    '\t\t\t\tlevel == 6 ? fw::KN7000_IRQ_SCHEDULER : fw::KN7000_IRQ_DISPATCH);\n')

# --- comment provenance that is only a firmware site -----------------------
CLEAN = [
    ('\t// voice record. The record array is 0x500AF940 + slot*0xB4 (128 slots; slots\n',
     '\t// voice record. The record array is fw::KN7000_VOICE_RECORDS + slot*0xB4; slots\n'),
    ('\t// note-on blit site 0x48494A5E).\n', '\t// note-on blit.\n'),
    ("\t// The firmware's 4-slot detector (the SoundRam probe at 0x48449EF4) validates\n",
     "\t// The firmware's four-slot detector validates\n"),
    ('\t// getters GetSDAudPlay_PLAYPAUSEFunc (0x48575084) / GetSDSndPlay_PLAYPAUSEFunc (0x485756E7) read these\n'
     '\t// state bytes via 0x485793b8 / 0x4857b33f: 1 = playing, 2 = paused, 0 = stopped. Light on play or pause.\n',
     '\t// state bytes (see fw:: above). Lit on either play or pause.\n'),
    ('\t// the per-TG-slot voice record sits at 0x5027AF1C rather than the KN6000\'s 0x5027AF28.\n',
     '\t// the per-TG-slot voice record sits one record earlier than the KN6000\'s.\n'),
    ('\t// (fw 0x48405028) reads register 0 and requires 0x20 to consider the DSP alive.\n',
     '\t// The boot probe reads register 0 and requires 0x20 to consider the DSP alive.\n'),
]
for old, new in CLEAN:
    if old in s:
        s = s.replace(old, new, 1)
    else:
        print('  (skip, not present) %r' % old.strip()[:60])

# the two sibling recbase assignments
s = re.sub(r'\tm_tg_recbase    = 0x5027AF28;[^\n]*\n(\t[ ]*// [^\n]*\n)?',
           '\tm_tg_recbase    = fw::KN6000_VOICE_RECORDS;\n', s, count=1)
s = re.sub(r'\tm_tg_recbase = 0x5027AF1C;[^\n]*\n',
           '\tm_tg_recbase = fw::KN6500_VOICE_RECORDS;\n', s, count=1)
s = s.replace('\t\tm_maincpu->set_maskable_vector(level, 0x90000000);',
              '\t\tm_maincpu->set_maskable_vector(level, fw::TRAMPOLINE_SLOT0);')

open(p, 'w').write(s)
print('centralised')
