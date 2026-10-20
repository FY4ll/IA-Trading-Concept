"""Page du vrai Graphify (code/graphify-out/graph.html) -> page d'artefact MOBILE D'ABORD (11/10/2026, demande de
l'utilisateur). Retire l'enveloppe html/head/body (ajoutée à la publication), titre, libellés en français, et ajoute :
sur téléphone, le graphe plein écran + un tiroir en bas (recherche toujours visible, détails/communautés repliables,
ouverture automatique au choix d'un point) ; sur ordinateur (>= 900 px), le panneau latéral d'origine.

    python atelier/outils/graphify_artefact.py <graph.html> <sortie.html>
Avant publication : vérifier qu'aucune valeur sensible de la config n'y figure (compteurs seulement).
"""
import re, sys

MOBILE_CSS = """
<style>
  /* mobile d'abord : graphe plein écran, tiroir en bas ; panneau latéral à partir de 900 px */
  html, body { height: 100%; }
  body { flex-direction: column; height: 100%; }
  #graph { flex: 1 1 auto; min-height: 0; }
  #sidebar { width: 100%; border-left: none; border-top: 1px solid #2a2a4e; max-height: 62vh;
             padding-bottom: env(safe-area-inset-bottom, 0px); transition: max-height .25s ease; }
  #sidebar.closed { max-height: calc(118px + env(safe-area-inset-bottom, 0px)); }
  #sheet-handle { display: flex; align-items: center; justify-content: space-between; gap: 10px; width: 100%;
                  background: none; border: 0; color: #aaa; padding: 8px 14px 2px; font: 600 12px -apple-system, "Segoe UI", sans-serif;
                  text-transform: uppercase; letter-spacing: .06em; cursor: pointer; }
  #sheet-handle::before { content: ""; position: absolute; left: 50%; transform: translateX(-50%); margin-top: -12px;
                          width: 40px; height: 4px; border-radius: 2px; background: #3a3a5e; }
  #sheet-handle span:last-child { color: #4E79A7; }
  #sheet-handle:focus-visible, #search:focus-visible { outline: 2px solid #4E79A7; outline-offset: 2px; }
  #sidebar { position: relative; }
  #search { font-size: 16px; padding: 10px 12px; }
  #search-results { max-height: 30vh; }
  .search-item, .legend-item { padding: 9px 6px; font-size: 14px; }
  .neighbor-link { padding: 7px 8px; font-size: 13px; }
  #info-panel { min-height: 0; }
  #sidebar.closed #info-panel, #sidebar.closed #legend-wrap, #sidebar.closed #stats { display: none; }
  #sidebar { overflow-y: auto; }
  #legend-wrap { flex: none; overflow: visible; }
  #neighbors-list { max-height: 34vh; }
  @media (min-width: 900px) {
    body { flex-direction: row; }
    #sidebar, #sidebar.closed { width: 300px; max-height: none; border-top: none; border-left: 1px solid #2a2a4e; padding-bottom: 0; }
    #sheet-handle { display: none; }
    #sidebar.closed #info-panel, #sidebar.closed #legend-wrap, #sidebar.closed #stats { display: block; }
    #legend-wrap { flex: 1; overflow-y: auto; }
    .search-item, .legend-item { padding: 4px 6px; font-size: 12px; }
    .neighbor-link { padding: 2px 6px; font-size: 12px; }
    #search { font-size: 13px; padding: 7px 10px; }
  }
  @media (prefers-reduced-motion: reduce) { #sidebar { transition: none; } }
</style>
"""

MOBILE_JS = """
<script>
(function () {
  const sb = document.getElementById('sidebar');
  const h = document.createElement('button');
  h.id = 'sheet-handle'; h.type = 'button';
  h.innerHTML = '<span>Carte du code</span><span>Détails ▲</span>';
  sb.prepend(h);
  const set = open => { sb.classList.toggle('closed', !open); h.lastChild.textContent = open ? 'Replier ▼' : 'Détails ▲';
                        h.setAttribute('aria-expanded', open); };
  set(!matchMedia('(max-width: 899px)').matches);
  h.addEventListener('click', () => set(sb.classList.contains('closed')));
  // un point choisi (toucher, recherche, voisin) ouvre le tiroir sur ses détails
  new MutationObserver(() => { if (sb.classList.contains('closed') && !document.querySelector('#info-content .empty')) set(true); })
    .observe(document.getElementById('info-content'), { childList: true });
  // le graphe se recadre quand la taille de sa zone change (rotation, tiroir)
  new ResizeObserver(() => { try { network.redraw(); } catch (e) {} }).observe(document.getElementById('graph'));
})();
</script>
"""

src, dst = sys.argv[1], sys.argv[2]
t = open(src, encoding="utf-8").read()
head = t[t.index("<head>") + 6:t.index("</head>")]
body = t[t.index("<body>") + 6:t.rindex("</body>")]
head = re.sub(r"<meta charset=\"UTF-8\">\s*", "", head)
head = re.sub(r"<title>.*?</title>\s*", "", head, flags=re.S)
head = head.replace("display: flex; height: 100vh; overflow: hidden;", "display: flex; height: 100vh; overflow: hidden; margin: 0;")
for a, b in [('placeholder="Search nodes..."', 'placeholder="Chercher une pièce..."'),
             ("<h3>Node Info</h3>", "<h3>Pièce choisie</h3>"),
             ("<h3>Communities</h3>", "<h3>Communautés</h3>"),
             (">Select All<", ">Tout afficher<"),
             ("Click a node to inspect it", "Toucher un point pour le lire"),
             (" nodes &middot; ", " pièces &middot; "), (" edges &middot; ", " liens &middot; "),
             (" communities</div>", " communautés</div>"),
             ("Type: ${", "Type : ${"), ("Community: ${", "Communauté : ${"), ("Source: ${", "Fichier : ${"),
             ("Degree: ${", "Liens : ${"), (">Neighbors (${", ">Voisins (${")]:
    if a not in body:
        print("libellé absent :", a)
    body = body.replace(a, b)
out = "<title>Graphe Run A</title>\n" + head.strip() + MOBILE_CSS + "\n" + body + MOBILE_JS
open(dst, "w", encoding="utf-8").write(out)
print("ok", len(out))
