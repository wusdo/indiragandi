/*
 * İNDİRAGANDİ — ExtendScript köprüsü
 * Premiere ve After Effects için içe aktarma
 */

function igHangiUygulama() {
    try {
        if (app && app.project && typeof app.project.importFiles === "function") return "PPRO";
        if (app && app.project && typeof app.project.importFile === "function") return "AEFT";
    } catch (e) {}
    return "?";
}

/* Premiere: yeni gelen klibi kök binde ara */
function igPremiereKlipBul(yol) {
    try {
        var kok = app.project.rootItem;
        var ara = function (bin) {
            for (var i = 0; i < bin.children.numItems; i++) {
                var it = bin.children[i];
                if (it.type === ProjectItemType.BIN) {
                    var b = ara(it);
                    if (b) return b;
                } else {
                    try {
                        var mp = it.getMediaPath();
                        if (mp && mp.replace(/\\/g, "/") === yol.replace(/\\/g, "/")) return it;
                    } catch (e) {}
                }
            }
            return null;
        };
        return ara(kok);
    } catch (e) { return null; }
}

/*
 * yol        : indirilen dosyanın tam yolu
 * zamanCizgi : "1" ise aktif sequence / comp üzerine de yerleştir
 */
function igIceAktar(yol, zamanCizgi) {
    try {
        var f = new File(yol);
        if (!f.exists) return "HATA|Dosya bulunamadi: " + yol;

        var uygulama = igHangiUygulama();

        /* ---------------- PREMIERE ---------------- */
        if (uygulama === "PPRO") {
            var hedefBin = app.project.rootItem;
            try {
                var ins = app.project.getInsertionBin();
                if (ins) hedefBin = ins;
            } catch (e) {}

            app.project.importFiles([yol], true, hedefBin, false);

            var klip = igPremiereKlipBul(yol);
            if (!klip) return "OK|Projeye eklendi";

            if (zamanCizgi === "1") {
                var seq = app.project.activeSequence;
                if (!seq) return "OK|Projeye eklendi (acik sequence yok)";
                try {
                    var konum = seq.getPlayerPosition();
                    var iz = null;
                    for (var i = 0; i < seq.videoTracks.numTracks; i++) {
                        if (!seq.videoTracks[i].isLocked()) { iz = seq.videoTracks[i]; break; }
                    }
                    if (!iz) iz = seq.videoTracks[0];
                    iz.overwriteClip(klip, konum.seconds);
                    return "OK|Sequence'e yerlestirildi";
                } catch (e2) {
                    return "OK|Projeye eklendi (timeline: " + e2.toString() + ")";
                }
            }
            return "OK|Projeye eklendi";
        }

        /* ---------------- AFTER EFFECTS ---------------- */
        if (uygulama === "AEFT") {
            app.beginUndoGroup("Indiragandi ice aktar");
            var io = new ImportOptions(f);
            try {
                if (io.canImportAs(ImportAsType.FOOTAGE)) io.importAs = ImportAsType.FOOTAGE;
            } catch (e3) {}
            var item = app.project.importFile(io);

            var mesaj = "Projeye eklendi";
            if (zamanCizgi === "1") {
                var comp = app.project.activeItem;
                if (comp && comp instanceof CompItem) {
                    comp.layers.add(item);
                    mesaj = "Comp'a katman olarak eklendi";
                } else {
                    mesaj = "Projeye eklendi (acik comp yok)";
                }
            }
            app.endUndoGroup();
            return "OK|" + mesaj;
        }

        return "HATA|Desteklenmeyen uygulama";
    } catch (err) {
        try { app.endUndoGroup(); } catch (e4) {}
        return "HATA|" + err.toString();
    }
}
