// Tiny external store so the test hook can crash the app shell on demand.
let crashed = false;
const subs = new Set<() => void>();

export const appCrashSignal = {
  get: () => crashed,
  subscribe(fn: () => void) {
    subs.add(fn);
    return () => subs.delete(fn);
  },
  trigger() {
    crashed = true;
    subs.forEach((f) => f());
  },
};
