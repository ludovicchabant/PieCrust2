
$(document).ready(function() {
    $('.ft-nav-collapsed + ul').hide();
});

if (!!window.EventSource) {
    var source = new EventSource('/bakelog');

    source.onerror = function(e) {
        console.log("Error with SSE, closing.", e);
        source.close();
    };
    source.addEventListener('message', function(e) {
        var msgEl = $('<div></div>');

        var removeMsgEl = function() {
            msgEl.remove();
            var bakelogEl = $('#ft-bakelog');
            if (bakelogEl.children().length == 0) {
                bakelogEl.hide();
            }
        };

        msgEl.addClass('alert-dismissible');
        msgEl.attr('role', 'alert');
        msgEl.append('<button type="button" class="close" data-dismiss="alert" aria-label="close">' +
                     '<span aria-hidden="true">&times;</span></button>');
        msgEl.append('<p>' + e.data + '</p>');
        var timeoutId = window.setTimeout(function() {
            msgEl.fadeOut(400, removeMsgEl);
        }, 4000);
        msgEl.mouseenter(function() {
            window.clearTimeout(timeoutId);
        });
        $('button', msgEl).click(removeMsgEl);

        var logEl = $('#ft-bakelog');
        logEl.append(msgEl);
        logEl.show();
    });
}


