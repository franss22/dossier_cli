let session = null;

let currentGroupIndex = 0;

let labels = {};
// { groupStartId: "Mastiff" }

let audio = new Audio();

const speakers = {
  1: "Mastiff",
  2: "May",
  3: "Mishima",
  4: "Morgan",
  5: "Moriarty",
};

async function loadSession() {
  const response = await fetch(
    "/api/session?recording_id=dg-session-4&transcription_id=abc123",
  );

  session = await response.json();

  audio.src = session.audio;

  renderCurrentGroup();
}

function getCurrentGroup() {
  return session.groups[currentGroupIndex];
}

function getGroupText(group) {
  return group.segment_ids.map((id) => session.segments[id].text).join(" ");
}

function renderCurrentGroup() {
  const group = getCurrentGroup();

  document.querySelector("#segment-text").textContent = getGroupText(group);

  document.querySelector("#progress").textContent =
    `${currentGroupIndex + 1}/${session.groups.length}`;

  playCurrentGroup();
}

function playCurrentGroup() {
  const group = getCurrentGroup();

  audio.currentTime = group.start;
  audio.play();
}

function assignSpeaker(name) {
  const group = getCurrentGroup();

  labels[group.start_id] = name;

  nextGroup();
}

function nextGroup() {
  if (currentGroupIndex >= session.groups.length - 1) {
    console.log("Finished!");
    return;
  }

  currentGroupIndex++;
  renderCurrentGroup();
}

function previousGroup() {
  if (currentGroupIndex <= 0) {
    return;
  }

  currentGroupIndex--;
  renderCurrentGroup();
}

function togglePlayback() {
  if (audio.paused) {
    audio.play();
  } else {
    audio.pause();
  }
}

function replayCurrent() {
  playCurrentGroup();
}

document.addEventListener("keydown", (event) => {
  const key = event.key;

  if (speakers[key]) {
    assignSpeaker(speakers[key]);
    return;
  }

  switch (key) {
    case " ":
      event.preventDefault();
      togglePlayback();
      break;

    case "ArrowRight":
      nextGroup();
      break;

    case "ArrowLeft":
      previousGroup();
      break;

    case "r":
      replayCurrent();
      break;
  }
});

loadSession();
