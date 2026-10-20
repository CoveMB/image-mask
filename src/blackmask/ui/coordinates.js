"use strict";
// All dimensions are oriented native pixels; screen units may differ from canvas units.
function viewTransform(size, crop, zoom, pan) {
  const width = crop[2] - crop[0],
    height = crop[3] - crop[1];
  const scale = Math.min(size[0] / width, size[1] / height) * zoom;
  return {
    scale,
    x: (size[0] - width * scale) / 2 + pan[0],
    y: (size[1] - height * scale) / 2 + pan[1],
  };
}
function screenToNative(client, rect, size, transform, crop, edge = false) {
  let x =
    (((client[0] - rect.left) * size[0]) / rect.width - transform.x) /
      transform.scale +
    crop[0];
  let y =
    (((client[1] - rect.top) * size[1]) / rect.height - transform.y) /
      transform.scale +
    crop[1];
  // Numerical roundoff at an exact rendered edge must not create a pixel outside a half-open crop.
  for (const bound of [crop[0], crop[2]])
    if (Math.abs(x - bound) < 1e-10) x = bound;
  for (const bound of [crop[1], crop[3]])
    if (Math.abs(y - bound) < 1e-10) y = bound;
  if (
    x < crop[0] ||
    y < crop[1] ||
    x > crop[2] ||
    y > crop[3] ||
    (!edge && (x === crop[2] || y === crop[3]))
  )
    return null;
  return [x, y];
}
function nativeBox(start, end) {
  return [
    Math.floor(Math.min(start[0], end[0])),
    Math.floor(Math.min(start[1], end[1])),
    Math.ceil(Math.max(start[0], end[0])),
    Math.ceil(Math.max(start[1], end[1])),
  ];
}
