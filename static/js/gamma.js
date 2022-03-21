function setupExamples() {
    var delay = 0;
    $('.example-group div.contents').each(function() {
        var contents = $(this);
        var header = $(this).siblings('h3');
        var wasOpen = readCookie(header.html());
        var visitedBefore = readCookie('visitedBefore');

        if (!visitedBefore) {
            createCookie('visitedBefore', true, 365);
        }

        if (!wasOpen || wasOpen === 'false') {
            if (!visitedBefore) {
                contents.delay(500 + delay).slideUp(500);
                delay += 100;
            }
            else {
                contents.hide();
            }
        }
        else {
            header.addClass('shown');
        }
    });

    $('.example-group').click(function(e) {
        var header = $(e.target);
        var contents = header.siblings('div.contents');

        contents.stop(false, true).slideToggle(500, function() {
            createCookie(header.html(), contents.is(':visible'), 365);
        });
        header.toggleClass('shown');
        header.siblings('i').toggleClass('shown');
	header.siblings('h3').toggleClass('shown');
    });
}

function evaluateCards() {
    var deferred = new $.Deferred();
    var requests = [];
    $('.result_card').each(function() {
        var card = Card.fromCardEl($(this));
        card.initSpecificFunctionality();
        // deferred if can evaluate, false otherwise
        var result = card.evaluate();
        if (!(result.state() == "rejected")) {
            requests.push(result);
        }
    });
    $.when.apply($, requests).then(function() {
        deferred.resolve();
    });
    return deferred;
}

$(document).ready(function() {
    evaluateCards().done(function() {
        setupExamples();
    });
});
