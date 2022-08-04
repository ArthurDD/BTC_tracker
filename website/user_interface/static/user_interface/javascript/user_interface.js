var socket;

function connect() {
    socket = new WebSocket('ws://' + window.location.host + '/ws/connect/');

    socket.onopen = function open() {
        display_banner("Connection to the server established!", "alert-success");
        setTimeout(function () {
            $('#submit_starting_btn').prop('disabled', false);  // Enables the submit button again
        }, 500);

        console.log('WebSockets connection created.');
    };

    let progress_bar_total = -1;
    let bar_width = 0;
    let req_made = 0;

    socket.onmessage = function (e) {
        let text_area = $('#terminal_output');
        const data = JSON.parse(e.data);
        let my_json;    // Will contain the json format of data.message if we expect a json format.
        let submit_btn = $('#submit_starting_btn')
        let text_area_val = text_area.val()

        switch (data.type) {
            case "connection_established":
                if (text_area.val() === "") {
                    text_area.val(data.message + "\n")  // We only write in the text_area when it's empty (i.e. when page is reloaded)
                }
                break;

            case "svg_file":    // Displays the graph and charts. Message sent once the analysis is finished and graph has been built
                $('#progress_div').hide()   // Hide the progress bar element
                display_graph(data.message['html_graph']);
                display_charts(data.message['html_charts']);
                display_stats(data.message['html_stats']);
                submit_btn.prop('disabled', false);
                break;

            case 'partial_svg_file':  // Displays the graph every time a layer is done
                display_graph(data.message);
                break;

            case 'error': // Message sent when address was not found
                submit_btn.prop('disabled', false);
                text_area_val = text_area.val();
                text_area.val(text_area_val + data.message + "\n");
                text_area.scrollTop(text_area[0].scrollHeight);
                break;

            case "progress_bar_start":      // Called at the beginning of each layer being parsed
                reset_progress_bar(true)        // Reset the loading bar
                my_json = JSON.parse(data.message)
                let total_layers = (parseInt($('#forward_layer_input').val()) + parseInt($('#backward_layer_input').val())).toString()
                $('#p_current_layer').html("Current layer: " + my_json['layer'].toString() + '/' + total_layers)
                progress_bar_total = my_json['total']
                bar_width = 0  // We need to reset progress bar and prepare it for the new layer coming
                break;

            case "progress_bar_update": // Sent every time a request is parsed in each layer.
                bar_width += data.message / progress_bar_total;
                let percentage = Math.min(Math.ceil(bar_width*100), 100)
                $('#progress_bar').css('width', percentage + '%')
                $('#p_current_progress').html(percentage + '%')
                break;

            case "waiting_bar":  // Display the waiting bar when requests failed and we need to wait
                display_waiting_bar(data.message);
                break;

            case "final_stats":  // Displays final stats when the parsing is done
                my_json = JSON.parse(data.message)
                let lines = "\n-------- FINAL RESULTS ---------\nTotal transactions parsed: " + my_json['total_txs']+ "\n" +
                    "Total time: " + my_json['total_time'] + "s\nRTO threshold: " +my_json["rto_threshold"] +
                    "\n\nRequests have been cached.\nAll done!"
                text_area_val = text_area.val();
                text_area.val(text_area_val + lines);
                text_area.scrollTop(text_area[0].scrollHeight);
                break;

            case "manual_tx":
                let url = 'display_manual_transactions/'
                $.post(url, {'data': data.message}, function (resp) {   // Make the request to display the modal /w txs
                    $('#modal_div').html(resp);  // load modal
                    $('#display_modal').click()  // display modal
                })
                break;

            case "ba_report":   // Message received when user wanted to display a ba report for an address and we get the answer from the backend
                let report = JSON.parse(data.message);
                display_ba_report(report);
                break;

            case "scraping_results":    // Receive a html file, so we just need to display it
                display_scraping_results(data.message)
                break;
            default:
                // console.log("Message: ", data.message)
                text_area_val = text_area.val();
                text_area.val(text_area_val + data.message + "\n");
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
    $('#graph').html(data)

    let counter = 0
    $('g.graph > g.node').each(function () {  // Cleaning the nodes and setting up the link to the anchor
        counter += 1
        let anchor = $(this).find('> g > a')
        if (anchor.length === 2) {
            let anchor_we = anchor.eq(0)    // First node <a> with the xlink corresponding to WE link
            let anchor_ba = anchor.eq(1)    // Second node <a> with the xlink corresponding to input_address for BA

            let anchor_we_href = anchor_we.attr("xlink:href")   // Get link
            let input_address = anchor_ba.attr("xlink:href")    // Get input_address

            anchor.removeAttr("xlink:href")     // Clean code
            anchor.removeAttr("xlink:title")    // Clean code
            anchor_we.attr('href', anchor_we_href)  // Set it up correctly

            let rto_elt = anchor_ba.find('text')
            let node_to_del = anchor_ba.parent()
            anchor_ba.parent().parent().append(rto_elt)
            node_to_del.remove()

            if (input_address !== "None") {
                rto_elt.attr('class', 'BA_search')
                rto_elt.attr('href', input_address)
            }
        }
    })

    $('.BA_search').click(function () {     // Set up the BA search when user clicks on a RTO line
        let input_address = $(this).attr('href')
        socket.send(JSON.stringify({
            'message': input_address,
            'type': 'ba_report',
        }));

    })

    $('div#graph').css('background-color', 'white')
    $('div#graph svg').attr('id', 'svg_graph')
    let svg = $('#svg_graph')
    svg.width("100%").height("100%")

    if ($('#graph_tab_content').hasClass('show')) {
        initialise_svg_pan_zoom()
    } else {
        $('#tab_bar li:first-child button').click(function () {
            if ($('#svg-pan-zoom-controls').length === 0) {   // Only initialise the svgPanZoom if it has not been before.
                initialise_svg_pan_zoom()
            }
        })
    }
}

function initialise_svg_pan_zoom () {
    const graph_zoom = svgPanZoom('#svg_graph', {
        zoomEnabled: true,
        controlIconsEnabled: true,
        fit: true,
        maxZoom: 30,
    });
}

function reset_graph() {    // Called when a new parsing is started.
    $('#stats').html('').hide();    // Hide the stats div

    // Sets back the default message
    $('#graph').html('<p style="margin-top:20px; font-style: italic"> The computed graph will appear here.</p>').css('background-color', '')
    svgPanZoom.destroy; // destroy svgPanZoom instance (can't have more than one in a page)
}

function display_banner(message, banner_class) {    // Manages all the different banners (about successful and lost connections)
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


function display_charts(data) {
    $('#chart').html(data)
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


function display_waiting_bar(secs_to_wait) {
    $('#waiting_bar').css('width', 0 + '%')
    $('#p_waiting_message').html('Waiting for ' + secs_to_wait + ' seconds to reset the request limit...')
    $('#p_wait_current_progress').html(0 + '%')
    let waiting_div = $('#waiting_div')
    waiting_div.show()   // Display the progress bar element
    let counter = 0;
    let bar_width = 0
    let waiting_interval = setInterval(function () {
        counter += 1
        bar_width = counter / secs_to_wait;
        let percentage = Math.min(Math.ceil(bar_width*100), 100)
        $('#waiting_bar').css('width', percentage + '%')
        $('#p_wait_current_progress').html(percentage + '%')
    }, 1000);
    setTimeout(function () {
        clearInterval(waiting_interval)
        waiting_div.hide();

    }, secs_to_wait*1000)
}


function dummy_function() {
    socket.send(JSON.stringify({
        'message': 'Dummy message',
        'type': 'json_conversion',
    }));
}


function resume_parsing(tx_to_remove) {
    // Called when the user finished selecting the transactions he wants to continue with in the parsing (manual mode)
    socket.send(JSON.stringify({
        'message': tx_to_remove,
        'type': 'resume_parsing',
    }));
}


function display_ba_report(report) {    // Called
    let new_report;
    if (report['found'] === false) {
         new_report = '<div class="report_div">' + '<div id="report_title" style="width: 100%; text-align: center; margin-bottom: 10px">Reports for <span class="report_colour">' + report["address"] + '</span></div>No report found.</div>'

    } else {
        new_report = "<div class=\"report_div\">" +
            "            <div id=\"report_title\" style=\"width: 100%; text-align: center; margin-bottom: 10px\">Reports for <span class=\"report_colour\">" + report['address'] + "</span></div>" +
            "            Total reports: <span class=\"report_colour\">" + report['total_report_count'] + "</span><br>" +
            "            Genuine recent reports: <span class=\"report_colour\">" + report['genuine_recent_count'] + "</span><br>" +
            "            Last reported: <span class=\"report_colour\">" + report['last_reported'] + "</span><br>"
        if (report['genuine_recent_count'] > 0) {
            new_report += "Categories of genuine recent reports: <span class=\"report_colour\">" + JSON.stringify(report['report_types']) + "</span> <br>" +
                "            <div class=\"genuine_recent_reports\" style=\"width: 100%\">\n" +
            "                <i><u>Genuine recent reports:</u></i><br>\n"

            for (let i=0; i < report['genuine_report'].length; i++) {
                let gen_report = report['genuine_report'][i]
                new_report += "                <span class=\"report_span\">" + i + "- " + gen_report + "</span><br>"

            }
        }

        new_report += "</div></div>"
    }
    new_report = $(new_report)
    new_report.insertAfter($('#reported_address_info'))

}


function display_stats (data) {  // Displays stats received once "get_stats" message has been sent.
    let stats_div = $('#stats')
    stats_div.html(data)
    stats_div.show()
}


function display_scraping_results(data) {
    $('#web_scraping').html(data)
    let tab_content = $('#tab_content')
    tab_content.scroll(function() {
        if ($('#web_scraping_div').css('display') !== 'none' ||
            $('#chart_tab_content').css('display') !== 'none') {     // Only activate this feature on the web_scraping tab and chart_tab
            scrollFunction();
        }
    })

    function scrollFunction() {
        let scroll_up_btn = $('#scroll_up_btn')
        if (tab_content.scrollTop() > 60) {  // || document.documentElement.scrollTop > 20) {
            scroll_up_btn.css('display', "block");
        } else {
            scroll_up_btn.css('display', "none");
        }
    }
}

// When the user clicks on the button, scroll to the top of the document
function go_top() {
  $('#tab_content').animate({ scrollTop: 0 }, 500);
}