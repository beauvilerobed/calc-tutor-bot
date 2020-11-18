var chatterbotUrl = '{% url "chatbot" %}';
var $chatlog = $('.js-chat-log');
var $input = $('.js-text');
var $sayButton = $('.js-say');

function createRow(text) {
  var $row = $('<li class="list-group-item"></li>');

  $row.text(text);
  $chatlog.append($row);
}

function submitInput() {
  var inputData = {
    'text': $input.val()
  }

  createRow(inputData.text);

  var $submit = $.ajax({
    type: 'POST',
    url: chatterbotUrl,
    data: JSON.stringify(inputData),
    contentType: 'application/json'
  });

  $submit.done(function(statement) {
      createRow(statement.text);
      $input.val('');
      $chatlog[0].scrollTop = $chatlog[0].scrollHeight;
  });

  $submit.fail(function(err) {
      console.error(err)
  });
}

$sayButton.click(function() {
  submitInput();
});

$input.keydown(function(event) {
  if (event.keyCode == 13) {
    submitInput();
  }
});