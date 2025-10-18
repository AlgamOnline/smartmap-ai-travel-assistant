let map;
let userLat = null;
let userLon = null;
let markers = [];

function initMap() {
  map = L.map("map").setView([-6.2, 106.816666], 13);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
  }).addTo(map);

  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        userLat = pos.coords.latitude;
        userLon = pos.coords.longitude;
        map.setView([userLat, userLon], 13);
        L.marker([userLat, userLon])
          .addTo(map)
          .bindPopup("📍 Lokasi Anda")
          .openPopup();
      },
      () => console.warn("Tidak bisa mengambil lokasi.")
    );
  }
}

// wail all page load before initMap
window.addEventListener("load", () => {
  initMap();
  document.getElementById("searchBtn").addEventListener("click", searchPlaces);
});
async function searchPlaces() {
  const query = document.getElementById("query").value.trim();
  if (!query) return alert("Enter search keywords!");

  const resultsDiv = document.getElementById("results");
  resultsDiv.innerHTML = `<p>🔄 Find Location...</p>`; // loading indicator

  try {
    const BACKEND_URL = "http://localhost:8000";

    const response = await fetch(`${BACKEND_URL}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: query, lat: userLat, lon: userLon }),
    });

    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

    const data = await response.json();
    console.log("Data from backend:", data);

    // clear marker
    markers.forEach((m) => map.removeLayer(m));
    markers = [];
    resultsDiv.innerHTML = "";

    if (!data.places || data.places.length === 0) {
      resultsDiv.innerHTML = "<p>❌ No results found.</p>";
      return;
    }

    data.places.forEach((p, idx) => {
      // Marker with name in popup detail
      const marker = L.marker([p.lat, p.lon])
        .addTo(map)
        .bindPopup(`<b>${p.name}</b><br>${p.address}<br><a href="${p.maps_link}" target="_blank">📍 Open in Google Maps</a>`);
      markers.push(marker);

      // List  sidebar
      const div = document.createElement("div");
      div.classList.add("place");
      div.innerHTML = `
        <h3>${idx + 1}. ${p.name}</h3>
        <p>${p.address}</p>
        ${p.distance_km ? `<p>📏 ${p.distance_km} km of your</p>` : ""}
        <a href="${p.maps_link}" target="_blank"> Open in Google Maps →</a>
      `;
      resultsDiv.appendChild(div);
    });

    map.fitBounds(L.featureGroup(markers).getBounds(), { padding: [30, 30] });
  } catch (err) {
    console.error(err);
    resultsDiv.innerHTML = "<p>⚠️ An error occurred while retrieving data..</p>";
  }
}



document.getElementById("searchBtn").addEventListener("click", searchPlaces);
