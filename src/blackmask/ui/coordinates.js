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

function nativeToScreen(point, rect, size, transform, crop) {
  return [
    rect.left + (transform.x + (point[0] - crop[0]) * transform.scale) * rect.width / size[0],
    rect.top + (transform.y + (point[1] - crop[1]) * transform.scale) * rect.height / size[1],
  ];
}
function spatialToNative(point, shape) {
  const angle = shape.rotation_degrees * Math.PI / 180, c = Math.cos(angle), s = Math.sin(angle);
  return [shape.center_xy[0] + c * point[0] - s * point[1], shape.center_xy[1] + s * point[0] + c * point[1]];
}
function spatialToLocal(point, shape) {
  const angle = shape.rotation_degrees * Math.PI / 180, c = Math.cos(angle), s = Math.sin(angle);
  const x = point[0] - shape.center_xy[0], y = point[1] - shape.center_xy[1];
  return [c * x + s * y, -s * x + c * y];
}
function spatialHandles(shape, oval) {
  const points = [{name: "center", local: [0, 0]}];
  if (oval) {
    const [a,b] = shape.inner_radii_xy;
    points.push({name: "radius-x", local: [a,0]}, {name: "radius-y", local: [0,b]},
      {name: "width", local: [a + shape.transition_width,0]},
      {name: "rotation", local: [a + shape.transition_width + Math.max(12,a/4),0]});
  } else {
    const span = shape.half_span, sigma = shape.fade_side === "positive" ? 1 : -1;
    points.push({name: "span-positive", local: [span,0]}, {name: "span-negative", local: [-span,0]},
      {name: "bend", local: [0,shape.bend]},
      {name: "width", local: [0,shape.bend + sigma * shape.transition_width]},
      {name: "rotation", local: [span + Math.max(12,span/4),0]});
    for (const sign of [-1,1]) {
      const u = sign * (span - shape.end_softness);
      points.push({name: sign < 0 ? "soft-negative" : "soft-positive", local: [u,shape.bend * (1 - (u/span)**2)]});
    }
  }
  return points.map(handle => ({name: handle.name, point: spatialToNative(handle.local, shape)}));
}
function hitSpatialHandle(point, handles, tolerance) {
  let best = null, distance = tolerance;
  for (const handle of handles) {
    const candidate = Math.hypot(point[0] - handle.point[0], point[1] - handle.point[1]);
    if (candidate <= distance) { best = handle; distance = candidate; }
  }
  return best;
}
