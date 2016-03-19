(function(){
  /*
  * Handling the removal of a path line
  */
  $(document).on('click', 'button[name=delete]', function(evt){
    evt.preventDefault();
    // Need to swap the names of this line with the last line
    var allButtons = $('button[name=delete]');
    var nodeToRemove = $(this).parent();
    var group = nodeToRemove.parent();

    // Don't delete if there's only one line
    if (group.find("div").length != 1) {
      nodeToRemove.remove();
    }

    var rows = group.find("div");

    var name = group.attr('id');
    console.log('name', name);
    var prefix = name.substr(0, name.indexOf('header-group'));
    rows.each(function(index, node){
        var main = $(node);
        var nodes = main.find("input[type=text]");
        nodes.attr('name', 'paths[]');
        if (index == 0 && rows.length == 1) {
          // remove the delete button if there's only one line left
          main.find("button").remove();
          nodes.attr('value', '');
        }
      });

  });
  /*
  * Adding path line when we edit the last line
  */
  var tmplElements = $('#paths-template').clone().removeAttr('id').removeClass('hidden');
  $(document).on('change paste keyup', 'input[type=text][name*="paths"]', function(evt){

    console.log(evt.target);
    var prefixName = this.name.substr(0, this.name.indexOf('['));
    console.log('prefixName:', prefixName);
    var elements = $('input[type=text][name^="' + prefixName +'"]');
    var last = elements.last().get(0);
    console.log('last', last);
    console.log('attr name', $(this).attr('name'));
    var lineElements = $('input[type=text][name="'+$(this).attr('name')+'"]');
    console.log(lineElements);
    var isLast = lineElements.filter(function(index, current){
      console.log(index, 'current', current, 'last', last, current == last);
        if (evt.target == current) {
          return current == last;
        } else {
          return false;
        }
    }).length != 0;
    console.log(isLast);
    // if we edited the last header line, add a new one
    if (isLast) {
      var newElements = tmplElements.clone();
      newElements.appendTo("#" + prefixName + "-group");
      newElements.find('input').attr('name', prefixName + '[]');
    }
  });
})();
