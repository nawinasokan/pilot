// var Alerts = JSON.parse('{{ Alert }}');
// if (Alerts) {
//     console.log(Alerts)
//     if (Alerts.Alert[type] == 'Success') {
//         toastr.info(Alerts.Alert[message], 'Success');
//     }
//     if (Alerts.Alert[type] == 'Info') {
//         toastr.info(Alerts.Alert[message], 'Info');
//     }
//     if (Alerts.Alert[type] == 'Warning') {
//         toastr.info(Alerts.Alert[message], 'Warning');
//     }
//     if (Alerts.Alert[type] == 'Error') {
//         toastr.info(Alerts.Alert[message], 'Error');
//     }
// }

// $('#content').hide();
// $('#loader').show();
// $(window).on('load', function () {
//     // $('#content').show();
//     // $('#loader').hide();
// })

$('#MiniRecords').click(function () {
  // status = $('#status').val();
  fromDate = $('#fromDate').val();
  toDate = $('#toDate').val();

  // sessionStorage.setItem('status', status);
  sessionStorage.setItem('fromDate', fromDate);
  sessionStorage.setItem('toDate', toDate);
});


(function ($) {
  'use strict';
  $(function () {
    $('#myTable').DataTable({
      "aLengthMenu": [
        [5, 10, 15, -1],
        [5, 10, 15, "All"]
      ],
      "iDisplayLength": 5,
      "language": {
        search: ""
      }
    });
    $('#myTable').each(function () {
      var datatable = $(this);
      // SEARCH - Add the placeholder for Search and Turn this into in-line form control
      var search_input = datatable.closest('.dataTables_wrapper').find('div[id$=_filter] input');
      search_input.attr('placeholder', 'Search');
      search_input.removeClass('form-control-sm');
      // LENGTH - Inline-Form control
      var length_sel = datatable.closest('.dataTables_wrapper').find('div[id$=_length] select');
      length_sel.removeClass('form-control-sm');
    });
  });
})(jQuery);

function datatablecall() {
  $('#myTable').DataTable({
    "aLengthMenu": [
      [5, 10, 15, -1],
      [5, 10, 15, "All"]
    ],
    "iDisplayLength": 5,
    "language": {
      search: ""
    }
  });
  $('#myTable').each(function () {
    var datatable = $(this);
    // SEARCH - Add the placeholder for Search and Turn this into in-line form control
    var search_input = datatable.closest('.dataTables_wrapper').find('div[id$=_filter] input');
    search_input.attr('placeholder', 'Search');
    search_input.removeClass('form-control-sm');
    // LENGTH - Inline-Form control
    var length_sel = datatable.closest('.dataTables_wrapper').find('div[id$=_length] select');
    length_sel.removeClass('form-control-sm');
  });
};
