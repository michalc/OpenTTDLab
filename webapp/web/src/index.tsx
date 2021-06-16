async function loadNative() {
  await import('xz');
  await import('./App');
}

loadNative();

export {}
