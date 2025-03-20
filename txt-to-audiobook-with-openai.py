import marimo

__generated_with = "0.11.20"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(__file__):
    from pathlib import Path

    OUTPUT_DIR = Path(__file__).parent / "output"

    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True)
    return OUTPUT_DIR, Path


@app.cell(hide_code=True)
def _(mo):
    file_selected = mo.ui.file(
        kind="area", filetypes=[".txt", ".rtf"], label="Input text files"
    )
    file_selected
    return (file_selected,)


@app.cell
def _(file_selected):
    input_file_content = None

    if file_selected.value:
        input_file_content = file_selected.contents().decode("utf-8-sig")
    return (input_file_content,)


@app.cell
async def _():
    import edge_tts

    voices = await edge_tts.list_voices()
    relevant_voices = [
        voice.get("ShortName")
        for voice in voices
        if voice.get("Locale") in ["en-US", "en-GB", "pl-PL"]
    ]
    relevant_voices
    return edge_tts, relevant_voices, voices


@app.cell
def _(file_selected):
    placeholder = "audiobook.mp3"
    if file_selected.value:
        placeholder = file_selected.name().replace(".txt", ".mp3")
    return (placeholder,)


@app.cell(hide_code=True)
def _(OUTPUT_DIR, mo, placeholder, relevant_voices):
    output_file_name = mo.ui.text(
        placeholder=placeholder, label=f"{str(OUTPUT_DIR)}\\", value=placeholder
    )

    voice_selector = mo.ui.dropdown(
        options=relevant_voices,
        label="Choose a voice",
        allow_select_none=False,
        searchable=True,
        value="en-US-BrianNeural",
    )
    return output_file_name, voice_selector


@app.cell(hide_code=True)
def _(mo, output_file_name, voice_selector):
    inputs_stack = mo.vstack(
        [voice_selector, output_file_name], gap="10px"
    )  # You can adjust the gap as needed

    inputs_stack
    return (inputs_stack,)


@app.cell
def _(
    OUTPUT_DIR,
    edge_tts,
    input_file_content,
    output_file_name,
    voice_selector,
):
    OUTPUT_FILE = OUTPUT_DIR / f"{output_file_name.value}"

    if input_file_content:
        communicate = edge_tts.Communicate(input_file_content, voice_selector.value)
        communicate.save_sync(str(OUTPUT_FILE))
        print(f"File saved to {str(OUTPUT_FILE)}")

    return OUTPUT_FILE, communicate


if __name__ == "__main__":
    app.run()
