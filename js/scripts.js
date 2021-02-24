(function ($) {
  "use strict"; // Start of use strict

  // Smooth scrolling using jQuery swing
  $('a.js-scroll-trigger[href*="#"]:not([href="#"])').click(function () {
    if (location.pathname.replace(/^\//, '') == this.pathname.replace(/^\//, '') && location.hostname == this.hostname) {
      var target = $(this.hash);
      target = target.length ? target : $('[name=' + this.hash.slice(1) + ']');
      if (target.length) {
        $('html, body').animate({
          scrollTop: (target.offset().top - 72)
        }, 500, "swing");
        return false;
      }
    }
  });

  // Closes responsive menu when a scroll trigger link is clicked
  $('.js-scroll-trigger').click(function () {
    $('.navbar-collapse').collapse('hide');
  });

  // Activate scrollspy to add active class to navbar items on scroll
  $('body').scrollspy({
    target: '#mainNav',
    offset: 75
  });

  // Embed note article
  $.ajax({
    url: 'https://api.tera-chan.com/api/ignore_cors/v1.php?resource=https://note.com/codefortoyama/rss',
    cache: false,
    dataType: 'xml',
    success: (xml) => {
      $(xml).find('item').each((index, element) => {
        if(index > 2){
          return false;
        }
        $('.note-row').append(
          '<div class="col-lg-4 col-sm-6 col-xs-12 mb-3">' +
          '<a class="card h-100 shadow text-left" href="' + $(element).find('link').text() + '" target="_blank" rel="noopener noreferrer">' +
          '<img src="' + $(element).find('media\\:thumbnail').text() + '" class="card-img-top" alt="">' +
          '<span class="card-body">' +
          '<h5 class="card-title">' + $(element).find('title').text() + '</h5>' +
          '<span class="d-flex justify-content-between align-items-center">' + '<span class="text-muted" style="font-size:11px;">' +
          '<span class="badge badge-success mr-1" style="background-color:#2cb696;">note</span>' +
          new Date($(element).find('pubDate').text()).toLocaleDateString() +
          '</span>' +
          '</span>' +
          '</a>' +
          '</div>'
        );
      });
    }
  });

})(jQuery); // End of use strict