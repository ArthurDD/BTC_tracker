var socket;

function connect() {
    socket = new WebSocket('ws://' + window.location.host + '/ws/connect/');

    socket.onopen = function open() {
        display_banner("Connection to the server established!", "alert-success");
        $('#submit_starting_btn').prop('disabled', false);  // Enables the submit button again

        console.log('WebSockets connection created.');
    };

    let progress_bar_total = -1;
    let bar_width = 0;

    socket.onmessage = function (e) {
        let text_area = $('#terminal_output');
        const data = JSON.parse(e.data);

        if (data.type === "connection_established") {
            if (text_area.val() === "") {
                text_area.val(data.message + "\n")
            }
        } else if (data.type === 'svg_file') {     // Displays the graph and charts. Message sent once the analysis is finished and graph has been built
            $('#progress_div').hide()   // Hide the progress bar element
            display_graph(data);
            display_charts();
            $('#submit_starting_btn').prop('disabled', false);

        } else if (data.type === 'error') {     // Message sent when address was not found
            $('#submit_starting_btn').prop('disabled', false);
            let val = text_area.val();
            text_area.val(val + data.message + "\n");
            text_area.scrollTop(text_area[0].scrollHeight);

        } else if (data.type === 'progress_bar_start') {    // Sent at the beginning of each layer before making requests
            reset_progress_bar(true)        // Reset the loading bar

            let my_json = JSON.parse(data.message)
            $('#p_current_layer').html("Current layer: " + my_json['layer'].toString() + '/' + $('#layer_input').val())
            progress_bar_total = my_json['total']
            bar_width = 0
            // We need to reset progress bar and prepare it for the new layer coming

        } else if (data.type === 'progress_bar_update') {   // Sent every time a request is parsed in each layer.
            bar_width += data.message / progress_bar_total;
            $('#progress_bar').css('width', Math.ceil(bar_width*100) + '%')
            $('#p_current_progress').html(Math.ceil(bar_width*100) + '%')

        } else if (data.type === 'final_stats') {   // Sent once the analysis is finished
            let my_json = JSON.parse(data.message)
            let lines = "\n-------- FINAL RESULTS ---------\nTotal transactions parsed: " + my_json['total_txs']+ "\n" +
                "Total time: " + my_json['total_time'] + "s\nRTO threshold: " +my_json["rto_threshold"] +
                "\n\nRequests have been cached.\nAll done!"
            let val = text_area.val();
            text_area.val(val + lines);
            text_area.scrollTop(text_area[0].scrollHeight);

        } else {
            let val = text_area.val();
            text_area.val(val + data.message + "\n");
            text_area.scrollTop(text_area[0].scrollHeight);
        }
    };

    socket.onclose = function (e) {
        display_banner("Connection to the server lost. Retrying in 2 sec...", "alert-warning");
        $('#submit_starting_btn').prop('disabled', true);  // Disables the submit button
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
        $('g.node > g > a').each(function () {
            let anchor_href = $(this).attr("xlink:href")
            $(this).removeAttr("xlink:href")
            $(this).removeAttr("xlink:title")
            $(this).attr('href', anchor_href)
        })
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

function reset_graph() {
    $('#graph').html('<p style="margin-top:20px; font-style: italic"> The computed graph will appear here.</p>').css('background-color', '')
    svgPanZoom.destroy; // destroy svgPanZoom instance (can't have more than one in a page)
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
        $('#chart').html(data)
    })
}

function set_height () {
    let main_height = $('body').outerHeight() - $('#nav_bar').outerHeight() + 'px'
    $('#main_content').css('height', main_height)
    // console.log('Main_height is: ', main_height)

    let total_height = $('#right_col').outerHeight()
    let header_height = $('#tab_bar').outerHeight()
    let height = total_height - header_height + 'px'
    $('#tab_content').css('height', height)
    // console.log("Height set to: ", height)
}


function reset_progress_bar(display) {
    $('#progress_bar').css('width', 0 + '%')
    $('#p_current_progress').html(0 + '%')
    $('#p_current_layer').html('')
    if (display) {
        $('#progress_div').show()   // Display the progress bar element
    } else {
        $('#progress_div').hide()   // Hide the progress bar element
    }
}

function dummy_function() {
    socket.send(JSON.stringify({
        'message': 'Dummy message',
        'type': 'json_conversion',
    }));
}
