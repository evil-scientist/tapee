#!/usr/bin/env python3
"""Render the parts listed in <parts_dir>/parts.json.

Run:  ~/tools/cadquery/bin/cq-python cad/render.py <parts_dir> <out_dir>

parts.json maps an image name to either
  {"title": ..., "parts": [{"file", "color", "kind"}, ...]}  -> outside 3/4 view + side cutaway
      (optional "camera": [x, y, z] for the outside view; default is front-left)
  {"title": ..., "grid": [name, ...]}                          -> grid (2 columns) of outside views of those entries
kind: "shell" (cut open in the cutaway), "outside" (cut open too), "inside" (only shown in the cutaway),
      "device" (always shown, never cut open, e.g. the printer).
"""
import json
import sys
from pathlib import Path

import vtk

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
manifest = json.loads((SRC / "parts.json").read_text())
W, H = 1600, 820
FOCAL = (0, 0, 60)
OUTSIDE_CAM = (-280, -360, 200)
CUTAWAY_CAM = (420, -60, 70)


def actor(entry, clip):
    r = vtk.vtkSTLReader()
    r.SetFileName(str(SRC / entry["file"]))
    src = r.GetOutputPort()
    if clip and entry["kind"] in ("shell", "outside"):
        plane = vtk.vtkPlane()
        plane.SetOrigin(0.01, 0, 0)
        plane.SetNormal(-1, 0, 0)  # keep x < 0, cut away the half nearer the camera
        c = vtk.vtkClipPolyData()
        c.SetInputConnection(src)
        c.SetClipFunction(plane)
        src = c.GetOutputPort()
    n = vtk.vtkPolyDataNormals()
    n.SetInputConnection(src)
    n.SetFeatureAngle(40)
    m = vtk.vtkPolyDataMapper()
    m.SetInputConnection(n.GetOutputPort())
    a = vtk.vtkActor()
    a.SetMapper(m)
    p = a.GetProperty()
    p.SetColor(*entry["color"][:3])
    if len(entry["color"]) > 3:
        p.SetOpacity(entry["color"][3])
    p.SetSpecular(0.25)
    p.SetSpecularPower(25)
    p.SetAmbient(0.18)
    if clip and entry["kind"] == "shell":
        back = vtk.vtkProperty()
        back.SetColor(*[c * 0.55 for c in entry["color"][:3]])
        a.SetBackfaceProperty(back)
    return a


def view(win, vp, entries, pos, clip, label, parallel=False):
    ren = vtk.vtkRenderer()
    ren.SetViewport(*vp)
    ren.SetBackground(0.95, 0.95, 0.96)
    ren.SetBackground2(0.84, 0.85, 0.88)
    ren.GradientBackgroundOn()
    for e in entries:
        if clip or e["kind"] != "inside":
            ren.AddActor(actor(e, clip))
    vtk.vtkLightKit().AddLightsToRenderer(ren)
    cam = ren.GetActiveCamera()
    cam.SetFocalPoint(*FOCAL)
    cam.SetPosition(*pos)
    cam.SetViewUp(0, 0, 1)
    if parallel:
        cam.ParallelProjectionOn()
    ren.ResetCamera()
    cam.Zoom(1.15)
    t = vtk.vtkTextActor()
    t.SetInput(label)
    t.SetPosition(14, 12)
    tp = t.GetTextProperty()
    tp.SetColor(0.2, 0.2, 0.25)
    tp.SetFontSize(20)
    ren.AddViewProp(t)
    win.AddRenderer(ren)


def save(win, name):
    win.Render()
    w = vtk.vtkWindowToImageFilter()
    w.SetInput(win)
    w.Update()
    png = vtk.vtkPNGWriter()
    png.SetFileName(str(OUT / f"{name}.png"))
    png.SetInputConnection(w.GetOutputPort())
    png.Write()
    print("wrote", OUT / f"{name}.png")


def window(h=H):
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetSize(W, h)
    win.SetMultiSamples(8)
    return win


for name, m in manifest.items():
    if "grid" in m:
        rows = (len(m["grid"]) + 1) // 2
        win = window(rows * H)
        for i, ref in enumerate(m["grid"]):
            x, y = i % 2, rows - 1 - i // 2
            view(win, (x / 2, y / rows, (x + 1) / 2, (y + 1) / rows), manifest[ref]["parts"],
                 manifest[ref].get("camera", OUTSIDE_CAM), False, manifest[ref]["title"])
        save(win, name)
    else:
        win = window()
        view(win, (0, 0, 0.5, 1), m["parts"], m.get("camera", OUTSIDE_CAM), False, m["title"])
        view(win, (0.5, 0, 1, 1), m["parts"], CUTAWAY_CAM, True,
             m.get("cutaway", "cutaway from the side: printer + Pi Zero W inside"), parallel=True)
        save(win, name)
