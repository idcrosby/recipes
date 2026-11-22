// Retire the old cache so returning visitors get the current cookbook.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => {
  event.waitUntil(Promise.all([
    caches.delete("pixyll2"),
    self.registration.unregister()
  ]));
});
