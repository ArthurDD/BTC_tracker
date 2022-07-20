var socket = new WebSocket('ws://' + window.location.host + '/ws/connect/');

socket.onopen = function open() {
  console.log('WebSockets connection created.');
};


socket.onmessage = function(e) {
    let text_area = $('#terminal_output')
    const data = JSON.parse(e.data);
    if (data.type === 'svg_file') {
        display_graph(data)
    } else {
        let val = text_area.val();
        text_area.val(val + data.message + "\n");
        // text_area.append('> ' + data.message + '\n');
        text_area.scrollTop(text_area[0].scrollHeight);
    }
};

socket.onclose = function(e) {
    console.error('Chat socket closed unexpectedly');
};


function display_graph(data) {
    let url = $('#starting_form').attr('action');

    $.get(url, {'file_name': data['svg_file_name']}, function (resp) {
        $('#graph').html(resp)
    }).then(function () {
        $('div#graph').css('background-color', 'white')
        $('div#graph svg').attr('id', 'svg_graph')
        let svg = $('#svg_graph')
        svg.width("100%").height("100%")

        window.zoomTiger = svgPanZoom('#svg_graph', {
            zoomEnabled: true,
            controlIconsEnabled: true,
            fit: true,
        });

        document.getElementById('enable').addEventListener('click', function() {
            window.zoomTiger.enableControlIcons();
        })
        document.getElementById('disable').addEventListener('click', function() {
            window.zoomTiger.disableControlIcons();
        })
        })
}


// $.post(url, form.serialize(), function (resp) {
//     $('#graph').html(resp)
//     {#console.log("response is: ", resp)#}
// }).then(function () {
//     $('div#graph svg').attr('id', 'svg_graph')
//     let svg = $('#svg_graph')
//     svg.width("100%").height("100%")
//
//     // Expose to window namespase for testing purposes
//     window.zoomTiger = svgPanZoom('#svg_graph', {
//         zoomEnabled: true,
//         controlIconsEnabled: true,
//         fit: true,
//         {#center: true,#}
//         // viewportSelector: document.getElementById('demo-tiger').querySelector('#g4') // this option will make library to misbehave. Viewport should have no transform attribute
//     });
//
//     document.getElementById('enable').addEventListener('click', function() {
//         window.zoomTiger.enableControlIcons();
//     })
//     document.getElementById('disable').addEventListener('click', function() {
//         window.zoomTiger.disableControlIcons();
//     })
// })
// return false
// })
// })