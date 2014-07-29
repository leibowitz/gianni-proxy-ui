(function(){
  /*
  * Handling the removal of a headers line
  */
  $(document).on('click', 'button[name=delete]', function(evt){
    evt.preventDefault();
    var nodeToRemove = $(this).parent();
    var group = nodeToRemove.parent();

    // Don't delete if there's only one line
    if (group.find("div").length != 1) {
      nodeToRemove.remove();
    }

    var rows = group.find("div");

    rows.each(function(index, node){
        var main = $(node);
        var nodesText = main.find("input[type=text]");
        var nodesCheck = main.find("input[type=checkbox]");
        nodesText.attr('name', 'rules_ids[' + index + ']');
        nodesCheck.attr('name', 'rules_states[' + index + ']');
        if (index == 0 && rows.length == 1) {
          // remove the delete button if there's only one line left
          main.find("button").remove();
          nodesText.attr('value', '');
        }
      });

  });

  /*
  * Adding headers line when we edit the last line
  */
  var tmplElements = $('#rules-template').clone().removeAttr('id').removeClass('hidden');
  $(document).on('change paste keyup', 'input[type=text][name*="rules_ids"]', function(evt){
    // get the prefix name, aka reqheader or respheader
    var prefixName = this.name.substr(0, this.name.indexOf('['));
    var elements = $('div#rules-group input[type=text][name^="' + prefixName +'"]');
    var last = elements.last().get(0);
    var lineElement = $(this);
    var isLast = lineElement.get(0) == last;
    // if we edited the last header line, add a new one
    if (isLast) {
      var newElements = tmplElements.clone();
      newElements.appendTo("#rules-group");
      newElements.find('input[type=text]').attr('name', 'rules_ids[' + elements.length + ']');
      newElements.find('input[type=checkbox]').attr('name', 'rules_states[' + elements.length + ']');
    }
  });
})();
