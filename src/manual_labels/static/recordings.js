let recordings = [];

async function loadRecordings() {
  const response = await fetch("/api/recordings");

  recordings = await response.json();

  renderRecordings();
}

function renderRecordings() {
  const container = document.getElementById("recordings");
  const singleTrackOnly = document.getElementById("singleTrackOnly").checked;

  container.innerHTML = "";

  const filtered = recordings.filter((recording) => {
    if (!singleTrackOnly) {
      return true;
    }

    return recording.tracks === 1;
  });

  if (filtered.length === 0) {
    container.innerHTML = "<p>No matching transcripts.</p>";
    return;
  }

  for (const recording of filtered) {
    container.appendChild(renderRecording(recording));
  }
}

function renderRecording(recording) {
  const card = document.createElement("div");

  card.className = "recording-card";

  const title = document.createElement("h3");
  title.textContent = recording.name;

  const info = document.createElement("p");

  info.textContent = `Recording: ${recording.recording_id}
         | Transcript: ${recording.transcription_id}
         | Tracks: ${recording.tracks}`;

  const button = document.createElement("button");

  button.textContent = "Label";

  button.onclick = () => {
    const url = new URL("/static/index.html", window.location.origin);

    url.searchParams.set("recording_id", recording.recording_id);

    url.searchParams.set("transcription_id", recording.transcription_id);

    window.location.href = url;
  };

  card.appendChild(title);
  card.appendChild(info);
  card.appendChild(button);

  return card;
}

document
  .getElementById("singleTrackOnly")
  .addEventListener("change", renderRecordings);

loadRecordings();
