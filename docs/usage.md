# Using ANYaudiobook

```sh
uv run python main.py [-d | --detach] [-l | --log]
```

The program opens a form in the terminal. Fill it in from top to bottom;
`tab` and `shift+tab` move between fields, `ctrl+q` quits.

## The form

| Field         | What to do                                                                                                                                                                                                |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ebook         | Paste or drop the file. Quoted paths, paths with escaped spaces (`My\ Book.epub`), `file://` URLs and `~` work. Once read, the line below shows the title, authors and how many chapters will be narrated |
| Output format | MP3 (a folder with a file per chapter) or M4B (one file with chapter markers, needs ffmpeg)                                                                                                               |
| Save as       | Suggested as `Author - Title` next to the ebook. Edit it freely: changing the format then only swaps the `.m4b` extension. A folder chosen for M4B gets `Author - Title.m4b` inside                       |
| Language      | Every language Edge TTS speaks, with its number of voices                                                                                                                                                 |
| Voice         | The chosen language's voices, with gender and region                                                                                                                                                      |
| Speed         | Slider, −50% (half as fast) to +100% (twice as fast), in steps of 5%                                                                                                                                      |
| Pitch         | Slider, −50 Hz to +50 Hz, in steps of 5 Hz                                                                                                                                                                |
| Volume        | Slider, −50% to +50%, in steps of 5%                                                                                                                                                                      |

In the lists, `↑`/`↓` (and `page up`/`page down`, `home`/`end`) move, `enter`
or `space` choose (the chosen entry is marked `●`), and typing a name jumps
to it. Choosing moves on to the next field; choosing a voice moves straight
to Convert, keeping the speed, pitch and volume as they were.

The sliders change the voice's own speed, pitch and volume; `┼` on the
track marks no change. `←`/`→` move a slider one step, `0` resets it, and
`enter` moves on. With the mouse, click the arrows to step or the track to
jump. Reach them with `tab` from the voice list, or `shift+tab` from Convert.

`ctrl+t` (or the Preview button) narrates the opening of the book, about
ten seconds, with the chosen voice and sliders, and plays it; `esc` stops
it. Change a slider and press `ctrl+t` again to compare. Playing needs an
audio player: `afplay` (built into macOS), `ffplay` (comes with ffmpeg),
`mpv` or `mpg123`, used in that order. The preview is narrated online, like
the audiobook, and is not saved.

`ctrl+s` (or the Convert button) starts the conversion; the form says what
is missing if it cannot. `ctrl+r` shows what will be narrated and skipped,
and why (see [filtering.md](filtering.md)).

The "Save as" line warns when an M4B would replace a file or MP3 chapters
would go into a folder that is not empty.

## Voices

The list of voices is downloaded from Microsoft every time the program
starts, in the background: the form is usable meanwhile, showing the list
saved last time. Without internet the saved list is used (converting needs
internet anyway).

## What is remembered

The output format, the language, the last voice used for each language,
and the speed, pitch and volume are saved when a conversion starts, and
chosen again next time: for another book with the same voice, paste its
path and press `ctrl+s`. They are
kept, with the saved list of voices, in `anyaudiobook.db` (SQLite) next to
`main.py`. Delete the file to forget them.

## Progress

The progress screen shows a bar (by characters narrated, with the time
left), which chapters are being narrated, and a log of each step. When it
is done, `n` goes back to the form for another book and `q` quits.

Pressing `q` while converting asks for a second `q` within three seconds,
which stops the conversion. Closing the terminal stops it too: use
`--detach` for long books.

## Running in the background: `--detach`

With `-d`/`--detach`, Convert starts the conversion as a separate process
and the program exits, printing the process id and where the audiobook
will be. The process runs in a session of its own (on Windows, without a
console), so the terminal can be closed. Use `--log` to follow it:

```sh
uv run python main.py --detach --log
tail -f "Jane Doe - Lorem Ipsum.log"
```

To stop it early, `kill <process id>`.

## Logs: `--log`

With `-l`/`--log`, a log is written next to the audio: `Author - Title.log`
beside an M4B, or inside the MP3 folder. It holds the job's settings, the
narrated/skipped report, a line per chapter started and finished, and the
traceback if the conversion fails. The form shows where it will go.

## Settings that are not in the form

`SETTINGS` at the top of `main.py`:

| Setting          | Default           | Meaning                                           |
| ---------------- | ----------------- | ------------------------------------------------- |
| `concurrency`    | `5`               | Chapters narrated at the same time                |
| `filter_options` | `FilterOptions()` | What to narrate, see [filtering.md](filtering.md) |

Unknown settings are an error, so a misspelt one does not go unnoticed.
Pitch, rate and volume used to be set here; they are now set in the form.
