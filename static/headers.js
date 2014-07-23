(function(){
  /*
  * Handling the removal of a headers line
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
    var prefix = name.substr(0, name.indexOf('header-group'));
    rows.each(function(index, node){
        var main = $(node);
        var nodes = main.find("input[type=text]");
        nodes.attr('name', prefix + 'header[' + index + '][]');
        if (index == 0 && rows.length == 1) {
          // remove the delete button if there's only one line left
          main.find("button").remove();
          nodes.attr('value', '');
        }
      });

  });
  /*
  * Adding headers line when we edit the last line
  */
  var tmplElements = $('#headers-template').clone().removeAttr('id').removeAttr('class');
  $(document).on('change paste keyup', 'input[type=text][name*="header"]', function(evt){
    // get the prefix name, aka reqheader or respheader
    var prefixName = this.name.substr(0, this.name.indexOf('['));
    var elements = $('input[type=text][name^="' + prefixName +'"]');
    var last = elements.last().get(0);
    var lineElements = $('input[type=text][name="'+$(this).attr('name')+'"]');
    var isLast = lineElements.filter(function(index, current){
        return current == last;
    }).length != 0;
    // if we edited the last header line, add a new one
    if (isLast) {
      var newElements = tmplElements.clone();
      newElements.appendTo("#" + prefixName + "-group");
      newElements.find('input').attr('name', prefixName + '['+(elements.length/2)+'][]');
    }
  });
})();
