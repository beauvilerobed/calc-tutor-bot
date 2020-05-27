// https://stackoverflow.com/questions/7151904/document-getelementbyid-returning-null
$(document).ready(function() {
// Get the modal
var modal = document.getElementById("myModal");
window.console&&console.log(modal);

// Get the button that opens the modal
var btn = document.getElementById("myBtn");
window.console&&console.log(btn);


// Get the <span> element that closes the modal
var span = document.getElementsByClassName("close")[0];

var dis = document.getElementsByClassName("steps").length;
window.console&&console.log(dis);
window.console&&console.log(dis[0]);

var dis2 = document.getElementsByClassName("result_card");
window.console&&console.log(dis2);

var dis3 = document.getElementsByClassName("result_card_error");
window.console&&console.log(dis3[0]);

// if(dis){
//   window.console&&console.log(dis2[2]);
// }

// When the user clicks the button, open the modal 
btn.onclick = function() {
  modal.style.display = "block";
}

// When the user clicks on <span> (x), close the modal
span.onclick = function() {
  modal.style.display = "none";
}

// When the user clicks anywhere outside of the modal, close it
window.onclick = function(event) {
  if (event.target == modal) {
    modal.style.display = "none";
  }
}

});