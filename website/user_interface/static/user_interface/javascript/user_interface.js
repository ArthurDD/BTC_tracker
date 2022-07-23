var socket;

function connect() {
    socket = new WebSocket('ws://' + window.location.host + '/ws/connect/');

    socket.onopen = function open() {
        display_banner("Connection to the server established!", "alert-success");
        $('#submit_starting_btn').prop('disabled', false);  // Enables the submit button again

        console.log('WebSockets connection created.');
    };


    socket.onmessage = function (e) {
        let text_area = $('#terminal_output');
        const data = JSON.parse(e.data);
        if (data.type === 'svg_file') {
            display_graph(data);
            display_charts();
            $('#submit_starting_btn').prop('disabled', false);
        } else if (data.type === 'error') {
            $('#submit_starting_btn').prop('disabled', false);
            let val = text_area.val();
            text_area.val(val + data.message + "\n");
            text_area.scrollTop(text_area[0].scrollHeight);
        } else {
            let val = text_area.val();
            text_area.val(val + data.message + "\n");
            text_area.scrollTop(text_area[0].scrollHeight);
        }
    };

    socket.onclose = function (e) {
        display_banner("Connection to the server lost. Retrying in 2 sec...", "alert-warning");
        setTimeout(function () {
            connect();
        }, 2000);
        console.error('Chat socket closed unexpectedly');
    };
}

connect()

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


function display_banner(message, banner_class) {
    let banner = $('#information_banner');
    banner.removeClass().addClass('fade show alert ' + banner_class);
    $('span', banner).removeClass();    // Remove the blink_me class

    $('span', banner).html(message);
    banner.show();

    if (banner_class === "alert-success") {
        setTimeout(function() {
            banner.fadeOut(500);
        }, 3000);
    } else {
        $('span', banner).addClass("blink_me");
    }
}


function display_charts() {
    $.get('/user_interface/display_charts/', function (data) {
        $('#chart_tab_content').html(data)
    })
}

function set_height () {
    let total_height = $('#right_col').outerHeight()
    let header_height = $('#tab_bar').outerHeight()
    let height = total_height - header_height + 'px'
    $('#tab_content').css('height', height)
    // console.log("Height set to: ", height)
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