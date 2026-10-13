"""Generate the proposed platform animation. Requires Pillow; does not start any services."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets"
WIDTH, HEIGHT = 1320, 940
BG = "#0b1026"


def font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts") / ("segoeuib.ttf" if bold else "segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu") / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default(size=size)


NODES = {
    "developer": (60, 180, "Developer", "Request a service in the portal", "Choose stack, team and resources", "#63c7ff", "01"),
    "portal": (510, 180, "Backstage", "Catalog + scaffolder + approvals", "One entry point for developers", "#b19aff", "02"),
    "github": (960, 180, "GitHub automation", "Repository + Actions + OIDC", "Plan, approve, build and scan", "#ff9bbb", "05"),
    "discovery": (60, 410, "Azure discovery", "Read-only inventory + allowlists", "Revalidate every resource choice", "#5ee3d0", "03"),
    "orchestrator": (510, 410, "Orchestrator", "API + independent worker", "Durable steps, retries and audit", "#ffb96b", "04"),
    "azure": (960, 410, "Azure infrastructure", "Terraform: approved changes", "Storage, identities and namespaces", "#63c7ff", "06"),
    "vault": (60, 640, "Azure Key Vault", "Dedicated secret management", "CSI files + Workload Identity", "#ffdf77", "KV"),
    "postgres": (510, 640, "PostgreSQL", "Separate service databases", "Workflow state + inbox + outbox", "#8bb6ff", "DB"),
    "aks": (960, 640, "AKS + starter app", "Docker image + Helm deployment", "NestJS dummy API / team service", "#a2e18e", "07"),
}

EDGES = {
    "request": ([(360, 240), (510, 240)], "#b19aff"),
    "submit": ([(660, 300), (660, 410)], "#ffb96b"),
    "validate": ([(510, 470), (360, 470)], "#5ee3d0"),
    "inventory": ([(210, 410), (210, 365), (1110, 365), (1110, 410)], "#5ee3d0"),
    "automation": ([(810, 445), (885, 445), (885, 240), (960, 240)], "#ff9bbb"),
    "provision": ([(1110, 300), (1110, 410)], "#63c7ff"),
    "deploy": ([(1110, 530), (1110, 640)], "#a2e18e"),
    "persist": ([(660, 530), (660, 640)], "#8bb6ff"),
    "vault_portal": ([(360, 675), (420, 675), (420, 335), (570, 335), (570, 300)], "#ffdf77"),
    "vault_worker": ([(360, 705), (445, 705), (445, 575), (575, 575), (575, 530)], "#ffdf77"),
    "vault_app": ([(210, 760), (210, 795), (1110, 795), (1110, 760)], "#ffdf77"),
}

SCENES = [
    ("Request", "Developer chooses an approved technology and deployment target.", ["request"], ["developer", "portal"]),
    ("Orchestrate", "Backstage submits the request; the API and worker manage its lifecycle.", ["submit", "persist"], ["portal", "orchestrator", "postgres"]),
    ("Validate", "Discovery checks resource selections against Azure inventory and allowlists.", ["validate", "inventory"], ["discovery", "azure", "orchestrator"]),
    ("Automate", "The worker coordinates repository creation, reviewed plans and application builds.", ["automation", "persist"], ["orchestrator", "github", "postgres"]),
    ("Provision", "Approved GitHub Actions use OIDC to apply the saved Terraform plan.", ["provision"], ["github", "azure"]),
    ("Deploy", "The selected stack becomes a Docker-ready starter and deploys through Helm.", ["deploy"], ["azure", "aks"]),
    ("Deliver secrets", "Key Vault supplies runtime secret files through CSI and Workload Identity.", ["vault_portal", "vault_worker", "vault_app"], ["vault", "portal", "orchestrator", "aks"]),
    ("Track progress", "Durable state and audit history support the provisioning status shown in Backstage.", ["persist", "submit"], ["postgres", "orchestrator", "portal"]),
]


def position(points, progress):
    lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
    remaining = progress * sum(lengths)
    for a, b, length in zip(points, points[1:], lengths):
        if remaining <= length:
            ratio = remaining / length
            return a[0] + (b[0] - a[0]) * ratio, a[1] + (b[1] - a[1]) * ratio
        remaining -= length
    return points[-1]


def render(scene_index, tick, ticks=14):
    im = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(im)
    for x in range(20, WIDTH, 36):
        for y in range(20, HEIGHT, 36):
            draw.ellipse((x, y, x + 1, y + 1), fill="#20263b")
    draw.rounded_rectangle((60, 38, 280, 66), radius=14, fill="#253356")
    draw.text((75, 41), "PROPOSED SOLUTION", font=font(16, True), fill="#abcfff")
    draw.text((60, 75), "Internal Developer Portal", font=font(42, True), fill="#f5f6ff")
    draw.text((62, 132), "Self-service applications  /  Guarded provisioning  /  Runtime secrets", font=font(22), fill="#bac4de")
    title, caption, active_edges, active_nodes = SCENES[scene_index]
    for key, (points, color) in EDGES.items():
        selected = key in active_edges
        draw.line(points, fill=color if selected else "#34405d", width=4 if selected else 2, joint="curve")
        a, b = points[-2:]
        angle = math.atan2(b[1] - a[1], b[0] - a[0])
        arrow = [b] + [(b[0] - 11 * math.cos(angle + offset), b[1] - 11 * math.sin(angle + offset)) for offset in (-0.45, 0.45)]
        draw.polygon(arrow, fill=color if selected else "#34405d")
        if selected:
            for shift in (0, 0.45):
                x, y = position(points, ((tick / ticks) + shift) % 1)
                draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill="#26344d")
                draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=color)
    for key, (x, y, name, line1, line2, color, number) in NODES.items():
        selected = key in active_nodes
        draw.rounded_rectangle((x + 5, y + 7, x + 305, y + 127), radius=19, fill="#060b1b")
        draw.rounded_rectangle((x, y, x + 300, y + 120), radius=18, fill="#171f3c", outline=color if selected else "#35415e", width=3 if selected else 1)
        draw.rounded_rectangle((x + 14, y + 14, x + 53, y + 44), radius=8, fill=color)
        draw.text((x + 22, y + 17), number, font=font(15, True), fill="#11162a")
        draw.text((x + 64, y + 14), name, font=font(21, True), fill=color)
        draw.text((x + 17, y + 61), line1, font=font(17), fill="#edf0ff")
        draw.text((x + 17, y + 88), line2, font=font(15), fill="#b5c1df")
    draw.text((689, 335), "Service API", font=font(14), fill="#bdc7e0")
    draw.text((682, 567), "State + audit", font=font(14), fill="#bdc7e0")
    draw.text((1134, 564), "Image + Helm", font=font(14), fill="#bdc7e0")
    draw.rounded_rectangle((60, 824, 1260, 918), radius=18, fill="#1b2545")
    draw.text((82, 839), f"{scene_index + 1:02d}  {title.upper()}", font=font(19, True), fill="#ffdf77")
    draw.text((82, 871), caption, font=font(19), fill="#eef1ff")
    for i in range(len(SCENES)):
        draw.rounded_rectangle((1040 + i * 25, 845, 1055 + i * 25, 853), radius=4, fill="#ffdf77" if i == scene_index else "#485472")
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frames = [render(scene, tick) for scene in range(len(SCENES)) for tick in range(14)]
    # A shared palette keeps the text and background stable across animation frames.
    palette = frames[0].quantize(colors=128)
    converted = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    converted[0].save(OUT / "proposed-platform.gif", save_all=True, append_images=converted[1:], duration=110, loop=0, optimize=True, disposal=1)
    frames[6 * 14].save(OUT / "proposed-platform-preview.png")
    print(OUT / "proposed-platform.gif")


if __name__ == "__main__":
    main()
