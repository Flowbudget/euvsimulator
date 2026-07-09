from manim import *

# ─── Palette ────────────────────────────────────────────────────
BG = "#0A0A0A"
PRIMARY = "#00F5FF"
SECONDARY = "#FF00FF"
ACCENT = "#39FF14"
TERTIARY = "#FFD93D"
MONO = "Menlo"

# ─── Scene 1: Title ─────────────────────────────────────────────
class Scene1_Title(Scene):
    def construct(self):
        self.camera.background_color = BG
        title = Text("OpEnUV", font_size=64, color=PRIMARY, weight=BOLD, font=MONO)
        subtitle = Text("From Plasma Source to CD Measurement",
                        font_size=28, color="#888888", font=MONO)
        subtitle.next_to(title, DOWN, buff=0.4)
        tagline = Text("Open EUV Lithography Simulator",
                       font_size=22, color=ACCENT, font=MONO)
        tagline.next_to(subtitle, DOWN, buff=0.3)
        logo = Circle(radius=0.15, color=SECONDARY, fill_opacity=0.8)
        logo.next_to(title, UP, buff=0.3)
        self.play(FadeIn(logo), Write(title), run_time=1.5)
        self.play(Write(subtitle), Write(tagline), run_time=1.2)
        self.wait(1.5)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.5)

# ─── Scene 2: EUV Light Source ──────────────────────────────────
class Scene2_LightSource(Scene):
    def construct(self):
        self.camera.background_color = BG
        # Droplet
        droplet = Circle(radius=0.3, color="#888888", fill_opacity=0.6)
        droplet.shift(LEFT * 2.5)
        lbl_drop = Text("Sn droplet", font_size=18, color="#888888", font=MONO)
        lbl_drop.next_to(droplet, DOWN, buff=0.3)
        # Laser arrow
        laser = Arrow(start=LEFT * 5, end=LEFT * 2.8, color=TERTIARY, stroke_width=6)
        lbl_laser = Text("CO2 laser", font_size=16, color=TERTIARY, font=MONO)
        lbl_laser.next_to(laser, UP, buff=0.1)
        # Plasma
        plasma = Circle(radius=0.5, color=SECONDARY, fill_opacity=0.4, stroke_color=PRIMARY)
        plasma.move_to(droplet.get_center())
        # EUV photons
        photons = VGroup(*[
            Dot(color=PRIMARY, radius=0.06).move_to(plasma.get_center() + RIGHT * 0.3 + UP * (i-2)*0.15)
            for i in range(5)
        ])
        # Labels
        eq = Text("λ = 13.5 nm", font_size=30, color=PRIMARY, font=MONO)
        eq.to_edge(UP, buff=0.5)
        ce = Text("CE ~ 5%", font_size=22, color=ACCENT, font=MONO)
        ce.next_to(eq, DOWN, buff=0.2)

        self.play(FadeIn(droplet), Write(lbl_drop), run_time=0.8)
        self.play(Create(laser), Write(lbl_laser), run_time=0.6)
        self.wait(0.3)
        self.play(ReplacementTransform(droplet.copy(), plasma), run_time=0.8)
        self.play(Write(eq), Write(ce), run_time=0.6)
        self.play(LaggedStart(*[FadeIn(p, scale=1.5) for p in photons], lag_ratio=0.1), run_time=1.0)
        self.wait(1.0)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.5)

# ─── Scene 3: Mask ──────────────────────────────────────────────
class Scene3_Mask(Scene):
    def construct(self):
        self.camera.background_color = BG
        # Build mask cross-section
        layers = VGroup()
        colors_layers = ["#444444", "#4A7FB5", "#6B8E23", "#8B4513", "#888888"]
        labels = ["Substrate", "Mo/Si ML (40-50×)", "Ru cap", "TaN absorber", "Hardmask"]
        y_start = -2
        for i, (c, l) in enumerate(zip(colors_layers, labels)):
            rect = Rectangle(width=6, height=0.25, color=c, fill_opacity=0.7)
            rect.move_to(UP * (y_start + i * 0.3))
            txt = Text(l, font_size=14, color=WHITE, font=MONO)
            txt.next_to(rect, RIGHT, buff=0.2)
            layers.add(rect, txt)
        # Arrows for bright/dark field
        arrow_bright = Arrow(start=UP * 2.5, end=UP * 1.8, color=PRIMARY, stroke_width=4)
        arrow_bright.shift(LEFT * 1.5)
        lbl_bright = Text("Bright", font_size=14, color=PRIMARY, font=MONO)
        lbl_bright.next_to(arrow_bright, UP, buff=0.05)
        arrow_dark = Arrow(start=UP * 2.5, end=UP * 1.8, color="#555555", stroke_width=4)
        arrow_dark.shift(RIGHT * 1.5)
        lbl_dark = Text("Dark", font_size=14, color="#555555", font=MONO)
        lbl_dark.next_to(arrow_dark, UP, buff=0.05)
        # Bragg label
        bragg = Text("2d sinθ = mλ", font_size=28, color=ACCENT, font=MONO)
        bragg.to_edge(DOWN, buff=0.4)

        self.play(FadeIn(layers, shift=UP), run_time=1.5)
        self.play(Create(arrow_bright), Write(lbl_bright), run_time=0.5)
        self.play(Create(arrow_dark), Write(lbl_dark), run_time=0.5)
        self.play(Write(bragg), run_time=0.6)
        self.wait(1.5)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.5)

# ─── Scene 4: Optics ────────────────────────────────────────────
class Scene4_Optics(Scene):
    def construct(self):
        self.camera.background_color = BG
        # Mirrors in a row (simple representation)
        mirrors = VGroup()
        for i in range(6):
            arc = ArcBetweenPoints(UP * 0.5 + RIGHT * (i-2.5), DOWN * 0.8 + RIGHT * (i-2.5),
                                   angle=-PI/2, color=PRIMARY, stroke_width=3)
            arc.rotate(PI)
            dot = Dot(RIGHT * (i-2.5), radius=0.08, color=SECONDARY)
            mirrors.add(arc, dot)
        mirrors.center()
        # Light path
        path = VGroup()
        for i in range(5):
            p = Line(start=RIGHT * (i-2.5), end=RIGHT * (i-1.5), color=TERTIARY, stroke_width=2, stroke_opacity=0.5)
            path.add(p)
        path.center()
        # Labels
        na_label = Text("NA 0.33 (Low-NA) / NA 0.55 (High-NA)", font_size=20, color=PRIMARY, font=MONO)
        na_label.to_edge(UP, buff=0.3)
        wfe = Text("WFE < 1 nm RMS", font_size=20, color=ACCENT, font=MONO)
        wfe.next_to(na_label, DOWN, buff=0.2)
        anam = Text("Anamorphic 4x / 8x (High-NA)", font_size=18, color="#888888", font=MONO)
        anam.next_to(wfe, DOWN, buff=0.2)

        self.play(Write(na_label), run_time=0.6)
        self.play(LaggedStart(*[Create(m) for m in mirrors], lag_ratio=0.1), run_time=1.5)
        self.play(Create(path), run_time=0.8)
        self.play(Write(wfe), Write(anam), run_time=0.6)
        self.wait(1.2)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.5)

# ─── Scene 5: Aerial Image ──────────────────────────────────────
class Scene5_AerialImage(Scene):
    def construct(self):
        self.camera.background_color = BG
        # Mask pattern
        mask_pattern = VGroup()
        for i in range(5):
            r = Rectangle(width=0.3, height=1.5, color="#555555", fill_opacity=0.8)
            r.move_to(LEFT * 2.5 + RIGHT * i * 0.6)
            mask_pattern.add(r)
        mask_pattern.shift(UP * 2)
        lbl_mask = Text("Mask", font_size=18, color=WHITE, font=MONO)
        lbl_mask.next_to(mask_pattern, UP, buff=0.15)
        # Arrows
        arrows = VGroup(*[Arrow(start=DOWN * 0.5 + m.get_center(), end=DOWN * 2.0, color=PRIMARY, stroke_width=2) 
                         for m in mask_pattern])
        # Intensity profile (approximate aerial image)
        axes = Axes(x_range=[-3, 3, 1], y_range=[0, 1.2, 0.2], x_length=6, y_length=2,
                    axis_config={"color": "#555555"})
        axes.shift(DOWN * 1.5 + LEFT * 0.3)
        graph = axes.plot(lambda x: 0.5 + 0.5 * np.cos(x * np.pi * 0.8), color=ACCENT, stroke_width=3)
        lbl_aerial = Text("Aerial Image", font_size=18, color=ACCENT, font=MONO)
        lbl_aerial.next_to(graph, DOWN, buff=0.15)

        self.play(FadeIn(mask_pattern), Write(lbl_mask), run_time=0.8)
        self.play(LaggedStart(*[Create(a) for a in arrows], lag_ratio=0.05), run_time=1.0)
        self.play(Create(axes), run_time=0.6)
        self.play(Create(graph), run_time=1.2)
        self.play(Write(lbl_aerial), run_time=0.4)
        self.wait(1.0)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.5)

# ─── Scene 6: Resist ────────────────────────────────────────────
class Scene6_Resist(Scene):
    def construct(self):
        self.camera.background_color = BG
        # Resist cross-section
        resist = Rectangle(width=6, height=1.2, color="#4A7FB5", fill_opacity=0.3)
        resist.shift(DOWN * 0.5)
        lbl_resist = Text("CAR (Chemically Amplified Resist)", font_size=18, color="#4A7FB5", font=MONO)
        lbl_resist.next_to(resist, UP, buff=0.1)
        # Photon
        photon = Dot(UP * 2, color=PRIMARY, radius=0.08)
        # Photoelectron
        pe = Dot(color=TERTIARY, radius=0.06)
        pe.move_to(resist.get_center() + LEFT * 1.5)
        # Secondary electrons
        ses = VGroup(*[
            Dot(color=ACCENT, radius=0.04).move_to(resist.get_center() + LEFT * 1.0 + UP * (i-2)*0.15)
            for i in range(5)
        ])
        # Acid diffusion area
        acid = Circle(radius=0.3, color=SECONDARY, fill_opacity=0.2)
        acid.move_to(resist.get_center())
        # Labels
        shot = Text("Photon Shot Noise", font_size=16, color=PRIMARY, font=MONO)
        shot.to_edge(DOWN, buff=0.3)
        sec = Text("Secondary e⁻ cascade", font_size=16, color=ACCENT, font=MONO)
        sec.to_edge(UP, buff=0.3)

        self.play(FadeIn(resist), Write(lbl_resist), run_time=0.8)
        self.play(FadeIn(photon), run_time=0.3)
        self.play(photon.animate.move_to(resist.get_top()), run_time=0.5)
        self.play(ReplacementTransform(photon.copy(), pe), run_time=0.4)
        self.play(LaggedStart(*[FadeIn(s) for s in ses], lag_ratio=0.1), run_time=0.8)
        self.play(Create(acid), run_time=0.5)
        self.play(Write(shot), Write(sec), run_time=0.5)
        self.wait(1.2)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.5)

# ─── Scene 7: Development & CD ──────────────────────────────────
class Scene7_Development(Scene):
    def construct(self):
        self.camera.background_color = BG
        # Resist profile after PEB
        profile = VGroup()
        for i in range(7):
            h = 0.2 + 0.8 * (1 - abs(i-3)/3.5)
            r = Rectangle(width=0.5, height=h, color=PRIMARY, fill_opacity=0.6)
            r.move_to(LEFT * 3 + RIGHT * i * 0.7 + DOWN * (1 - h/2))
            profile.add(r)
        lbl_profile = Text("Developed Resist Profile", font_size=18, color=PRIMARY, font=MONO)
        lbl_profile.next_to(profile, UP, buff=0.2)
        # CD measurement arrow
        cd_arrow = DoubleArrow(start=LEFT * 0.7, end=RIGHT * 2.1, color=ACCENT, stroke_width=4)
        cd_arrow.shift(DOWN * 0.5)
        cd_label = Text("CD = 32 nm", font_size=28, color=ACCENT, font=MONO)
        cd_label.next_to(cd_arrow, DOWN, buff=0.2)
        # Bossung plot
        axes = Axes(x_range=[-60, 60, 20], y_range=[20, 50, 10], x_length=4, y_length=2.5,
                    axis_config={"color": "#555555"})
        axes.to_edge(RIGHT, buff=0.5).shift(UP * 0.5)
        bossung = axes.plot(lambda x: 32 + 0.05 * x**2, color=SECONDARY, stroke_width=3)
        lbl_bossung = Text("Process Window", font_size=16, color=SECONDARY, font=MONO)
        lbl_bossung.next_to(axes, DOWN, buff=0.1)

        self.play(FadeIn(profile), Write(lbl_profile), run_time=1.0)
        self.play(Create(cd_arrow), Write(cd_label), run_time=0.8)
        self.play(Create(axes), Create(bossung), run_time=1.0)
        self.play(Write(lbl_bossung), run_time=0.4)
        self.wait(1.0)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.5)

# ─── Scene 8: Architecture ──────────────────────────────────────
class Scene8_Architecture(Scene):
    def construct(self):
        self.camera.background_color = BG
        # Module boxes
        modules = ["source", "mask3d", "optics", "aerial", "resist", "metro"]
        boxes = VGroup()
        for i, mod in enumerate(modules):
            box = Rectangle(width=2, height=0.6, color=PRIMARY, fill_opacity=0.15)
            box.move_to(UP * (1 - i * 0.6) + LEFT * 2.5)
            txt = Text(mod, font_size=18, color=PRIMARY, font=MONO)
            txt.move_to(box.get_center())
            boxes.add(box, txt)
        # Pipeline arrow
        pipeline = VGroup()
        for i in range(5):
            a = Arrow(start=LEFT * 1.5 + UP * (1 - i * 0.6 - 0.3),
                      end=LEFT * 1.5 + UP * (1 - (i+1) * 0.6 + 0.3),
                      color="#555555", stroke_width=2)
            a.set_opacity(0.3)
            pipeline.add(a)
        # CLI commands
        cli_cmds = VGroup()
        cmds = ["euv simulate", "euv process-window", "euv serve"]
        for i, cmd in enumerate(cmds):
            t = Text(f"$ {cmd}", font_size=20, color=ACCENT, font=MONO)
            t.move_to(RIGHT * 2.5 + DOWN * (i * 0.7))
            cli_cmds.add(t)
        cli_title = Text("CLI", font_size=22, color=ACCENT, font=MONO)
        cli_title.next_to(cli_cmds, UP, buff=0.3)
        # Github
        url = Text("github.com/Flowbudget/OpEnUV", font_size=18, color="#555555", font=MONO)
        url.to_edge(DOWN, buff=0.3)
        # Title
        title = Text("Architecture", font_size=36, color=PRIMARY, weight=BOLD, font=MONO)
        title.to_edge(UP, buff=0.3)

        self.play(Write(title), run_time=0.6)
        self.play(LaggedStart(*[FadeIn(b, shift=RIGHT*0.5) for b in boxes], lag_ratio=0.1), run_time=1.5)
        self.play(Create(pipeline), run_time=0.6)
        self.play(Write(cli_title), run_time=0.3)
        self.play(LaggedStart(*[Write(c) for c in cli_cmds], lag_ratio=0.15), run_time=0.8)
        self.play(Write(url), run_time=0.4)
        self.wait(1.5)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.5)