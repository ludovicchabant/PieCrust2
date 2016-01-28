
$(document).ready(function() {
    $('.ft-nav-collapsed + ul').hide();
});

var onPublishEvent = function(e) {
    var msgEl = $('<div></div>');

    var removeMsgEl = function() {
        msgEl.remove();
        var publogEl = $('#ft-publog');
        if (publogEl.children().length == 0) {
            publogEl.hide();
        }
    };

    msgEl.addClass('alert-dismissible');
    msgEl.attr('role', 'alert');
    msgEl.append('<button type="button" class="close" data-dismiss="alert" aria-label="close">' +
                 '<span aria-hidden="true">&times;</span></button>');
    msgEl.append('<div>' + e.data + '</div>');
    var timeoutId = window.setTimeout(function() {
        msgEl.fadeOut(400, removeMsgEl);
    }, 4000);
    msgEl.mouseenter(function() {
        window.clearTimeout(timeoutId);
    });
    $('button', msgEl).click(removeMsgEl);

    var logEl = $('#ft-publog');
    logEl.append(msgEl);
    logEl.show();
};

if (!!window.EventSource) {
    var source = new EventSource('/publish-log');
    source.onerror = function(e) {
        console.log("Error with SSE, closing.", e);
        source.close();
    };
    source.addEventListener('message', onPublishEvent);
}

