///////////////////////////////////////////////////////////////////////////////
// PieCrust debug info and features
//
// This stuff is injected by PieCrust's preview server and shouldn't show up
// in production. It should all be self-contained in this one file.
///////////////////////////////////////////////////////////////////////////////

var eventSource = new EventSource("/__piecrust_debug/pipeline_status");

if (eventSource != null) {
    eventSource.onerror = function(e) {
        console.log("Error with SSE, closing.", e);
        eventSource.close();
    };

    eventSource.addEventListener('ping', function(e) {
    });

    eventSource.addEventListener('pipeline_success', function(e) {
        var obj = JSON.parse(e.data);
        console.log("Got pipeline success", obj);

        // Check which assets were processed, and whether they are referenced
        // by the current page for the usual use-cases.
        for (var i = 0; i < obj.assets.length; ++i) {
            a = obj.assets[i];
            if (assetReloader.reloadAsset(a)) {
                notification.flashSuccess("Reloaded " + a);
            }
        }
    });

    eventSource.addEventListener('pipeline_error', function(e) {
        var obj = JSON.parse(e.data);
        console.log("Got pipeline error", obj);

        var outer = document.createElement('div');
        outer.style = 'padding: 1em;';
        for (var i = 0; i < obj.assets.length; ++i) {
            var item = obj.assets[i];
            var markup = (
                '<p>Error processing: <span style="font-family: monospace;">' +
                item.path + '</span></p>\n' +
                '<ul>');
            for (var j = 0; j < item.errors.length; ++j) {
                markup += (
                    '<li style="font-family: monospace;">' + 
                    item.errors[j] +
                    '</li>\n');
            }
            markup += '</ul>\n';
            var entry = document.createElement('div');
            entry.innerHTML = markup;
            outer.appendChild(entry);
        }

        var placeholder = document.getElementById('piecrust-debug-info-pipeline-status');
        placeholder.appendChild(outer);
    });
}

///////////////////////////////////////////////////////////////////////////////

NotificationArea = function() {
    var area = document.createElement('div');
    area.id = 'piecrust-debug-notifications';
    area.className = 'piecrust-debug-notifications';
    document.querySelector('body').appendChild(area);

    this._area = area;
    this._lastId = 0;
};

NotificationArea.prototype.flashSuccess = function(msg) {
    this.flashMessage(msg, 'success');
};

NotificationArea.prototype.flashError = function(msg) {
    this.flashMessage(msg, 'error');
};

NotificationArea.prototype.flashMessage = function(msg, css_class) {
    this._lastId += 1;
    var thisId = this._lastId;
    this._area.insertAdjacentHTML(
            'afterbegin',
            '<div id="piecrust-debug-notification-msg' + thisId + '" ' +
                  'class="piecrust-debug-notification ' +
                       'piecrust-debug-notification-' + css_class + '">' +
                msg + '</div>');

    window.setTimeout(this._discardNotification, 2000, thisId);
};

NotificationArea.prototype._discardNotification = function(noteId) {
    var added = document.querySelector('#piecrust-debug-notification-msg' + noteId);
    added.remove();
};

///////////////////////////////////////////////////////////////////////////////

function _get_extension(name) {
    var ext = null;
    var dotIdx = name.lastIndexOf('.');
    if (dotIdx > 0)
        ext = name.substr(dotIdx + 1);
    return ext;
}

function _get_basename(name) {
    var filename = name;
    var slashIdx = name.lastIndexOf('/');
    if (slashIdx > 0)
        filename = name.substr(slashIdx + 1);
    return filename;
}

var _regex_cache_bust = /\?\d+$/;

function _is_path_match(path1, path2) {
    path1 = path1.replace(_regex_cache_bust, '');
    console.log("Matching:", path1, path2)
    return path1.endsWith(path2);
};

function _add_cache_bust(path, cache_bust) {
    path = path.replace(_regex_cache_bust, '');
    return path + cache_bust;
}

///////////////////////////////////////////////////////////////////////////////

AssetReloader = function() {
    this._imgExts = ['jpg', 'jpeg', 'png', 'gif', 'svg'];
    this._imgReloader = new ImageReloader();
    this._cssReloader = new CssReloader();
};

AssetReloader.prototype.reloadAsset = function(name) {
    var ext = _get_extension(name);
    var filename = _get_basename(name);

    if (ext == 'css') {
        return this._cssReloader.reloadStylesheet(filename);
    }
    if (this._imgExts.indexOf(ext) >= 0) {
        return this._imgReloader.reloadImage(filename);
    }

    console.log("Don't know how to reload", filename);
    return false;
};

///////////////////////////////////////////////////////////////////////////////

CssReloader = function() {
};

CssReloader.prototype.reloadStylesheet = function(name) {
    var result = false;
    var sheets = document.styleSheets;
    var cacheBust = '?' + new Date().getTime();
    for (var i = 0; i < sheets.length; ++i) {
        var sheet = sheets[i];
        if (_is_path_match(sheet.href, name)) {
            sheet.ownerNode.href = _add_cache_bust(sheet.href, cacheBust);
            result = true;
        }
    }
    return result;
};

///////////////////////////////////////////////////////////////////////////////

ImageReloader = function() {
    this._imgStyles = [
          { selector: 'background', styleNames: ['backgroundImage'] },
        ];
    this._regexCssUrl = /\burl\s*\(([^)]+)\)/;
};

ImageReloader.prototype.reloadImage = function(name) {
    var result = false;
    var imgs = document.images;
    var cacheBust = '?' + new Date().getTime();
    for (var i = 0; i < imgs.length; ++i) {
        var img = imgs[i];
        if (_is_path_match(img.src, name)) {
            img.src = _add_cache_bust(img.src, cacheBust);
            result = true;
        }
    }
    for (var i = 0; i < this._imgStyles.length; ++i) {
        var imgInfo = this._imgStyles[i];
        var domImgs = document.querySelectorAll(
                "[style*=" + imgInfo.selector + "]");
        for (var j = 0; j < domImgs.length; ++j) {
            var img = domImgs[j];
            result |= this._reloadStyleImage(img.style, imgInfo.styleNames,
                                             name, cacheBust);
        }
    }
    for (var i = 0; i < document.styleSheets.length; ++i) {
        var styleSheet = document.styleSheets[i];
        result |= this._reloadStylesheetImage(styleSheet, name, cacheBust);
    }
    return result;
};

ImageReloader.prototype._reloadStyleImage = function(style, styleNames, path,
                                                     cacheBust) {
    var result = false;
    for (var i = 0; i < styleNames.length; ++i) {
        var value = style[styleNames[i]];
        if ((typeof value) == 'string') {
            m = this._regexCssUrl.exec(value);
            if (m != null) {
                var m_clean = m[1].replace(/^['"]/, '');
                m_clean = m_clean.replace(/['"]$/, '');
                if (_is_path_match(m_clean, path)) {
                    m_clean = _add_cache_bust(m_clean, cacheBust);
                    style[styleNames[i]] = 'url("' + m_clean + '")';
                    result = true;
                }
            }
        }
    }
    return result;
};

ImageReloader.prototype._reloadStylesheetImage = function(styleSheet, path,
                                                          cacheBust) {
    try {
        var rules = styleSheet.cssRules;
    } catch (e) {
        // Things like remote CSS stylesheets (e.g. a Google Fonts ones)
        // will triger a SecurityException here, so just ignore that.
        return;
    }

    var result = false;
    for (var i = 0; i < rules.length; ++i) {
        var rule = rules[i];
        switch (rule.type) {
            case CSSRule.IMPORT_RULE:
                result |= this._reloadStylesheetImage(rule.styleSheet, path,
                                                      cacheBust);
                break;
            case CSSRule.MEDIA_RULE:
                result |= this._reloadStylesheetImage(rule, path, cacheBust);
                break;
            case CSSRule.STYLE_RULE:
                for (var j = 0; j < this._imgStyles.length; ++j) {
                    var imgInfo = this._imgStyles[j];
                    result |= this._reloadStyleImage(
                            rule.style, imgInfo.styleNames, path, cacheBust);
                }
                break;
        }
    }
    return result;
};

///////////////////////////////////////////////////////////////////////////////

function toggleDebugInfo() {
    var info = document.querySelector('.piecrust-debug-info');
    if (info.classList.contains('piecrust-debug-info-unloaded')) {
        loadDebugInfo();
        info.classList.remove('piecrust-debug-info-unloaded');
    }
    if (this.innerHTML == '[+]') {
        this.innerHTML = '[-]';
        info.style = "";
    } else {
        this.innerHTML = '[+]';
        info.style = "display: none;";
    }
}

function loadDebugInfo() {
    var xmlHttp = new XMLHttpRequest();

    xmlHttp.onreadystatechange = function() {
        if (xmlHttp.readyState == XMLHttpRequest.DONE) {
            var info = document.querySelector('.piecrust-debug-info');
            if(xmlHttp.status < 500) {
                info.innerHTML = xmlHttp.responseText;
            }
            else {
                console.log(xmlHttp);
                info.innerHTML = "Unknown error.";
            }
        }
    }

    var pageUrl = window.location.pathname;
    xmlHttp.open("GET", "/__piecrust_debug/debug_info?page=" + pageUrl, true);
    xmlHttp.send();
}

///////////////////////////////////////////////////////////////////////////////

var notification = new NotificationArea();
var assetReloader = new AssetReloader();

window.onload = function() {
    var cacheBust = '?' + new Date().getTime();

    var style = document.createElement('link');
    style.rel = 'stylesheet';
    style.type = 'text/css';
    style.href = '/__piecrust_static/piecrust-debug-info.css' + cacheBust;
    document.head.appendChild(style);

    var expander = document.querySelector('.piecrust-debug-expander');
    expander.onclick = toggleDebugInfo;
};


window.onbeforeunload = function(e) {
    if (eventSource != null)
        eventSource.close();
};

