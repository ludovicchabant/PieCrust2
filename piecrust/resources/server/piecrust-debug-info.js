var eventSource = new EventSource("/__piecrust_debug/pipeline_status");

//window.onbeforeunload = function(e) {
//    console.log("Disconnecting SSE.", e);
//    eventSource.close();
//};

eventSource.onerror = function(e) {
    console.log("Error with SSE, closing.", e);
    eventSource.close();
};

eventSource.addEventListener('pipeline_success', function(e) {
    var placeholder = document.getElementById('piecrust-debug-info-pipeline-status');
    //if (placeholder.firstChild !== null)
    placeholder.removeChild(placeholder.firstChild);
});

eventSource.addEventListener('pipeline_error', function(e) {
    var obj = JSON.parse(e.data);

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

