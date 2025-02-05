import { createApp } from 'vue';
import * as codex from 'codex';
import * as codexIcons from 'codex-icons';
import Session, { set } from 'm3api/browser.js';
import { addCommentLabel, initializeRegionCommentList, labelLocalQualifierStatement } from './shared.js'

function setup() {
    'use strict';
    const csrfTokenElement = document.getElementById('csrf_token'),
          baseUrl = document.querySelector('link[rel=index]').href.replace(/\/$/, ''),
          depictedProperties = JSON.parse(document.getElementsByTagName('main')[0].dataset.depictedProperties);

    /** Make a key event handler that calls the given callback when Esc is pressed. */
    function onEscape(callback) {
        return function(eKey) {
            if (eKey.key === 'Escape') {
                return callback.apply(this, arguments);
            }
        };
    }

    function addEditButtons() {
        document.querySelectorAll('.wd-image-positions--depicted-without-region').forEach(addEditButton);
        document.querySelectorAll('.wd-image-positions--depicted-without-region').forEach(addRemoveButton);
    }

    function addEditButton(element) {
        const entity = element.closest('.wd-image-positions--entity'),
              depictedId = element.firstChild.dataset.entityId,
              scaleInput = entity.querySelector('.wd-image-positions--scale'),
              wrapper = entity.querySelector('.wd-image-positions--wrapper'),
              image = wrapper.firstElementChild;

        const button = document.createElement('button');
        button.type = 'button';
        button.classList.add('btn', 'btn-secondary', 'btn-sm', 'ms-2');
        button.textContent = 'add region';
        button.addEventListener('click', onClick);
        element.append(button);

        let cropper = null;
        let doneCallback = null;
        const onKeyDown = onEscape(cancelEditing);
        let cancelButton = null;

        function onClick() {
            if (cropper === null) {
                button.textContent = 'loading...';
                wrapper.classList.add('wd-image-positions--active');
                image.classList.add('wd-image-positions--active');
                button.classList.add('wd-image-positions--active');
                scaleInput.disabled = true;
                doneCallback = ensureImageCroppable(image);
                cropper = new Cropper(image.firstElementChild, {
                    viewMode: 2,
                    movable: false,
                    rotatable: true, // we don’t rotate the image ourselves, but this allows cropper.js to respect JPEG orientation
                    scalable: false,
                    zoomable: false,
                    checkCrossOrigin: false,
                    autoCrop: false,
                    ready: function() {
                        button.textContent = 'use this region';

                        cancelButton = document.createElement('button');
                        cancelButton.type = 'button';
                        cancelButton.classList.add('btn', 'btn-secondary', 'btn-sm', 'wd-image-positions--active', 'ms-2');
                        cancelButton.textContent = 'cancel';
                        cancelButton.addEventListener('click', cancelEditing);
                        element.append(cancelButton);
                    },
                });
                document.addEventListener('keydown', onKeyDown);
            } else {
                if (button.textContent === 'loading...') {
                    return;
                }
                const cropData = cropper.getData();
                if (!cropData.width || !cropData.height) {
                    window.alert('Please select a region first. (Drag the mouse across an area, then adjust as needed.)');
                    return;
                }

                const depicted = document.createElement('div');
                depicted.classList.add('wd-image-positions--depicted')
                const propertyId = [...element.closest('.wd-image-positions--depicteds-without-region').classList]
                      .filter(klass => klass.startsWith('wd-image-positions--depicteds-without-region__'))
                      .map(klass => klass.slice('wd-image-positions--depicteds-without-region__'.length))[0];
                depicted.dataset.statementId = element.dataset.statementId;
                if (depicted.dataset.statementId.includes("Q")) {
                    depicted.classList.add(`wd-image-positions--depicted__${propertyId}`)
                } else {
                    depicted.classList.add(`wd-image-positions--depicted__local`)
                }
                if (depictedId !== undefined) {
                    depicted.dataset.entityId = depictedId;
                }

                depicted.append(element.firstChild.cloneNode(true));
                image.append(depicted);
                button.textContent = 'editing statement…';
                const subject = { id: entity.dataset.entityId, domain: entity.dataset.entityDomain };
                saveCropper(subject, image, depicted, cropper).then(
                    function() {
                        element.remove();
                        if (image.querySelectorAll('.wd-image-positions--depicted').length === 1) {
                            addEditRegionButton(entity);
                        }
                    },
                    function() {
                        element.remove();
                    },
                ).then(doneCallback).finally(() => {
                    document.removeEventListener('keydown', onKeyDown);
                    scaleInput.disabled = false;
                });
                cropper = null;
            }
        }

        function cancelEditing() {
            cropper.destroy();
            cropper = null;
            doneCallback();
            wrapper.classList.remove('wd-image-positions--active');
            image.classList.remove('wd-image-positions--active');
            document.removeEventListener('keydown', onKeyDown);
            button.textContent = 'add region';
            button.classList.remove('wd-image-positions--active');
            scaleInput.disabled = false;
            if (cancelButton !== null) {
                cancelButton.remove();
                cancelButton = null;
            }
        }
    }

    function addRemoveButton(element) {
        if (element.dataset.statementId.includes("Q")) {
            return 
        }

        const button = document.createElement('button');
        button.type = 'button';
        button.classList.add('btn', 'btn-secondary', 'btn-sm', 'ms-2');
        button.textContent = 'delete statement';
        button.addEventListener('click', onClick);
        element.append(button);

        function onClick() {
            const statementId = element.dataset.statementId,
                  formData = new FormData();
            formData.append('statement_id', statementId);
            element.remove()
            fetch(`${baseUrl}/api/v1/delete_statement_local`, {
                method: 'POST',
                body: formData,
                credentials: 'include',
            }).then(response => {
                if (response.ok) {
                   
                } else {
                    window.alert(`An error occurred: deleting statement with id ${statementId} failed. This could be because it is not a local statement.`);
                    throw new Error('Deleting failed');
                }
            });
        }
    }

    function addCommentLabelsOwnUser() {
        // get base level information
        const formData = new FormData();
        const entityDiv = document.querySelector(".wd-image-positions--entity");
        const itemId = entityDiv.getAttribute('data-entity-id');
        formData.append('item_id', itemId);
    
        // fetch comments
        return fetch(`${baseUrl}/api/v2/get_comments_own_user`, {
            method: 'POST',
            body: formData,
            credentials: 'include',
        }).then(response => {
            if (response.ok) {
                return response.json().then(json => {
                    json.forEach(item => addCommentLabel(item.statement_id, item.project_lead_username, item.comment))
                });
            } else {
                return response.text().then(error => {
                    window.alert(`An error occurred:\n\n${error}`);
                });
            }
        });
   
   }

    /**
     * Ensure that the image element is suitable for cropper.js,
     * by temporarily changing its src to the last (presumed highest-resolution) srcset entry.
     * The srcset is assumed to contain PNG/JPG thumbs,
     * whereas the src may be in an unsupported image format, such as TIFF.
     *
     * @param {HTMLElement} image The .wd-image-positions--image containing the <img>
     * (*not* the <img> itself)
     * @return {function} Callback to restore the image to its original src,
     * to be called after the cropper has been destroyed.
     */
    function ensureImageCroppable(image) {
        const img = image.querySelector('img'),
              originalSrc = img.src;

        if (!/\.(?:jpe?g|png|gif)$/i.test(originalSrc)) {
            img.src = img.srcset.split(' ').slice(-2)[0];
        }

        return function() {
            img.src = originalSrc;
        };
    }

    /**
     * Save the cropper as a region qualifier for the depicted.
     *
     * @param {{ id: string, domain: string}} subject The subject entity
     * @param {HTMLElement} image The .wd-image-positions--image (*not* the <img>)
     * @param {HTMLElement} depicted The .wd-image-positions--depicted,
     * with a dataset containing a statementId, optional entityId and optional qualifierHash
     * @param {Cropper} cropper The cropper (will be destroyed)
     * @return {Promise}
     */
    function saveCropper(subject, image, depicted, cropper) {
        const wrapper = image.parentElement;
        wrapper.classList.remove('wd-image-positions--active');
        image.classList.remove('wd-image-positions--active');
        const cropData = cropper.getData(),
              canvasData = cropper.getCanvasData(),
              x = 100 * cropData.x / canvasData.naturalWidth,
              y = 100 * cropData.y / canvasData.naturalHeight,
              w = 100 * cropData.width / canvasData.naturalWidth,
              h = 100 * cropData.height / canvasData.naturalHeight;
        // note: the browser rounds the percentages a bit,
        // and we’ll use the rounded values for the IIIF region
        depicted.style.left = `${x}%`;
        depicted.style.top = `${y}%`;
        depicted.style.width = `${w}%`;
        depicted.style.height = `${h}%`;
        cropper.destroy();
        function pct(name) {
            return depicted.style[name].replace('%', '');
        }
        const iiifRegion = `pct:${pct('left')},${pct('top')},${pct('width')},${pct('height')}`;

        const statementId = depicted.dataset.statementId,
              qualifierHash = depicted.dataset.qualifierHash,
              csrfToken = csrfTokenElement.textContent,
              formData = new FormData();
        formData.append('statement_id', statementId);
        if (qualifierHash) {
            formData.append('qualifier_hash', qualifierHash);
        }
        formData.append('iiif_region', iiifRegion);
        formData.append('_csrf_token', csrfToken);
        return fetch(`${baseUrl}/api/v2/add_qualifier_local/${subject.domain}`, {
            method: 'POST',
            body: formData,
            credentials: 'include',
        }).then(response => {
            if (response.ok) {
                return response.json().then(json => {
                    depicted.dataset.qualifierHash = json.qualifier_hash;
                });
            } else {
                return response.text().then(text => {
                    window.alert(`An error occurred:\n\n${text}\n\nThe region drawn is ${iiifRegion}, if you want to add it manually.`);
                    throw new Error('Saving failed');
                });
            }
        });
    }

    function addEditRegionButtons() {
        document.querySelectorAll('.wd-image-positions--entity').forEach(addEditRegionButton);
    }

    function addEditRegionButton(entityElement) {
        const wrapper = entityElement.querySelector('.wd-image-positions--wrapper'),
              image = wrapper.firstElementChild;
        if (!image.querySelector('.wd-image-positions--depicted')) {
            return;
        }
        const scaleInput = entityElement.querySelector('.wd-image-positions--scale');
        const button = document.createElement('button');
        button.type = 'button';
        button.classList.add('btn', 'btn-secondary');
        button.textContent = 'Edit a region';
        button.addEventListener('click', addEditRegionListeners);
        const cancelButton = document.createElement('button');
        cancelButton.type = 'button';
        cancelButton.classList.add('btn', 'btn-secondary', 'wd-image-positions--active', 'ms-2');
        cancelButton.textContent = 'cancel';
        const buttonWrapper = document.createElement('div');
        buttonWrapper.append(button);
        addRemoveRegionButton(entityElement, buttonWrapper)
        // cancelButton is not appended yet
        entityElement.append(buttonWrapper);
        const fieldSet = entityElement.querySelector('fieldset');
        if (fieldSet) {
            entityElement.append(fieldSet); // move after buttonWrapper
        }
        let onKeyDown = null;

        function addEditRegionListeners() {
            button.textContent = 'Select a region to edit';
            button.classList.add('wd-image-positions--active');
            for (const depicted of entityElement.querySelectorAll('.wd-image-positions--depicted')) {
                depicted.addEventListener('click', editRegion);
            }
            button.removeEventListener('click', addEditRegionListeners);
            onKeyDown = onEscape(cancelSelectRegion);
            document.addEventListener('keydown', onKeyDown);
            buttonWrapper.append(cancelButton);
            cancelButton.addEventListener('click', cancelSelectRegion);
        }

        function editRegion(event) {
            event.preventDefault();
            wrapper.classList.add('wd-image-positions--active');
            image.classList.add('wd-image-positions--active');
            scaleInput.disabled = true;
            for (const depicted of entityElement.querySelectorAll('.wd-image-positions--depicted')) {
                depicted.removeEventListener('click', editRegion);
            }
            const depicted = event.target.closest('.wd-image-positions--depicted');
            document.removeEventListener('keydown', onKeyDown);
            cancelButton.removeEventListener('click', cancelSelectRegion);
            onKeyDown = onEscape(cancelEditRegion);
            document.addEventListener('keydown', onKeyDown);
            cancelButton.addEventListener('click', cancelEditRegion);
            const doneCallback = ensureImageCroppable(image);
            const cropper = new Cropper(image.firstElementChild, {
                viewMode: 2,
                movable: false,
                rotatable: true, // we don’t rotate the image ourselves, but this allows cropper.js to respect JPEG orientation
                scalable: false,
                zoomable: false,
                checkCrossOrigin: false,
                ready: function() {
                    const canvasData = cropper.getCanvasData();
                    cropper.setData({
                        x: Math.round(parseFloat(depicted.style.left) * canvasData.naturalWidth / 100),
                        y: Math.round(parseFloat(depicted.style.top) * canvasData.naturalHeight / 100),
                        width: Math.round(parseFloat(depicted.style.width) * canvasData.naturalWidth / 100),
                        height: Math.round(parseFloat(depicted.style.height) * canvasData.naturalHeight / 100),
                    });
                    button.textContent = 'use this region';
                    button.addEventListener('click', doEditRegion);
                },
            });

            function doEditRegion() {
                button.removeEventListener('click', doEditRegion);
                button.textContent = 'editing statement…';
                const subject = { id: entityElement.dataset.entityId, domain: entityElement.dataset.entityDomain };
                saveCropper(subject, image, depicted, cropper).then(
                    function() {
                        button.textContent = 'Edit a region';
                        button.classList.remove('wd-image-positions--active');
                        button.addEventListener('click', addEditRegionListeners);
                    },
                    function() {
                        button.textContent = 'Edit a region';
                        button.classList.remove('wd-image-positions--active');
                        button.addEventListener('click', addEditRegionListeners);
                    },
                ).then(doneCallback).finally(() => {
                    document.removeEventListener('keydown', onKeyDown);
                    scaleInput.disabled = false;
                    cancelButton.remove();
                });
            }

            function cancelEditRegion() {
                cropper.destroy();
                doneCallback();
                wrapper.classList.remove('wd-image-positions--active');
                image.classList.remove('wd-image-positions--active');
                button.removeEventListener('click', doEditRegion);
                button.textContent = 'Edit a region';
                button.addEventListener('click', addEditRegionListeners);
                button.classList.remove('wd-image-positions--active');
                document.removeEventListener('keydown', onKeyDown);
                scaleInput.disabled = false;
                cancelButton.remove();
            }
        }

        function cancelSelectRegion() {
            for (const depicted of entityElement.querySelectorAll('.wd-image-positions--depicted')) {
                depicted.removeEventListener('click', editRegion);
            }
            button.textContent = 'Edit a region';
            button.addEventListener('click', addEditRegionListeners);
            button.classList.remove('wd-image-positions--active');
            document.removeEventListener('keydown', onKeyDown);
            cancelButton.remove();
        }
    }

    function addRemoveRegionButton(entityElement, buttonWrapper) {
        const wrapper = entityElement.querySelector('.wd-image-positions--wrapper');
        const button = document.createElement('button');
        button.type = 'button';
        button.classList.add('btn', 'btn-secondary');
        button.textContent = 'Remove a region';
        button.addEventListener('click', addDeleteRegionListeners);
        buttonWrapper.append(button)

        let onKeyDown = null;
        let cancelButton = null;
        cancelButton = document.createElement('button');
        cancelButton.type = 'button';
        cancelButton.classList.add('btn', 'btn-secondary', 'btn-sm', 'wd-image-positions--active', 'ms-2');
        cancelButton.textContent = 'cancel';

        function addDeleteRegionListeners() {
            button.textContent = 'Select a region to remove';
            button.classList.add('wd-image-positions--active');
            for (const depicted of entityElement.querySelectorAll('.wd-image-positions--depicted')) {
                depicted.addEventListener('click', deleteRegion);
            }
            button.removeEventListener('click', addDeleteRegionListeners);
            
            cancelButton.addEventListener('click', cancelDeleteRegion);
            buttonWrapper.append(cancelButton);
        }

        function deleteRegion(event) {
            event.preventDefault();
            for (const depicted of entityElement.querySelectorAll('.wd-image-positions--depicted')) {
                depicted.removeEventListener('click', deleteRegion);
            }
            
            const depicted = event.target.closest('.wd-image-positions--depicted');
            const statementId = depicted.getAttribute("data-statement-id"),
                  formData = new FormData();
            formData.append("statement_id", statementId)
            depicted.remove()
            fetch(`${baseUrl}/api/v2/delete_qualifier_local`, {
                method: 'POST',
                body: formData,
                credentials: 'include',
            }).then(response => {
                if (response.ok) {
                    return response.json().then(json => {
                        const statementId = json.depicted.statement_id;
                        const propertyId = json.depicted.property_id;
                        let depictedsWithoutRegionList = entityElement.querySelector(
                            `.wd-image-positions--depicteds-without-region__${propertyId} ul`,
                        );
                        if (!depictedsWithoutRegionList) {
                            const depictedsWithoutRegionDiv = document.createElement('div'),
                                    depictedsWithoutRegionText = document.createTextNode(
                                        `${depictedProperties[propertyId]?.[1] || propertyId} with no region specified:`,
                                    );
                            depictedsWithoutRegionList = document.createElement('ul');
                            depictedsWithoutRegionDiv.classList.add('wd-image-positions--depicteds-without-region');
                            depictedsWithoutRegionDiv.classList.add(`wd-image-positions--depicteds-without-region__${propertyId}`);
                            depictedsWithoutRegionDiv.append(depictedsWithoutRegionText, depictedsWithoutRegionList);
                            const newDepictedFormRoot = document.getElementById('new-depicted-form-root')
                            newDepictedFormRoot.insertAdjacentElement('beforebegin', depictedsWithoutRegionDiv);
                        }
                        const new_depicted = document.createElement('li');
                        new_depicted.classList.add('wd-image-positions--depicted-without-region');
                        new_depicted.dataset.statementId = statementId;
                        new_depicted.innerHTML = json.depicted_item_link;
                        depictedsWithoutRegionList.append(new_depicted);
                        addEditButton(new_depicted);
                        if (!String(statementId).includes("Q")) {
                            addRemoveButton(new_depicted);
                        }
                    });
                    
                } else {
                    window.alert(`An error occurred: deleting qualifier with statement id ${statementId} failed. This may be because it is a qualifier that has already been posted on wikidata.`);
                    throw new Error('Deleting failed');
                }
            });

            cancelDeleteRegion()
        }

        function cancelDeleteRegion() {
            for (const depicted of entityElement.querySelectorAll('.wd-image-positions--depicted')) {
                depicted.removeEventListener('click', deleteRegion);
            }
            button.textContent = 'Remove a region';
            button.addEventListener('click', addDeleteRegionListeners);
            document.removeEventListener('keydown', onKeyDown);
            cancelButton.remove();
        }
    }

    function addUploadButton(element) {
        const formData = new FormData();
        const entityDiv = document.querySelector(".wd-image-positions--entity");
        const itemId = entityDiv.getAttribute('data-entity-id');
        formData.append('item_id', itemId);

        fetch(`${baseUrl}/api/v2/get_approved`, {
            method: 'POST',
            body: formData,
            credentials: 'include',
        }).then(response => {
            if (response.ok) {
                response.json().then(json => {
                    if (json[0]['approved'] == 0) {
                        return;
                    }
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.classList.add('btn', 'btn-secondary');
                    button.setAttribute('id', "approve-button")
                    button.textContent = 'Upload to Wikidata';
                    button.addEventListener('click', onClick);
                    element.prepend(button);
                });
              
            } else {
                return response.text().then(error => {
                    window.alert(`An error occurred:\n\n${error}`);
                });
            }
        });

        function onClick() {
            return fetch(`${baseUrl}/api/v2/upload_annotations`, {
                method: 'POST',
                body: formData,
                credentials: 'include',
            }).then(response => {
                if (response.ok) {
                    document.querySelectorAll(".wd-image-positions--depicteds-without-region__P180").forEach(e => e.remove());
                    document.querySelector('#approve-button').remove();
                    document.querySelectorAll(".wd-image-positions--depicted__P180").forEach(e => e.remove());
                    alert("Uploaded to Wikidata!");
                    return;
                } else {
                    return response.text().then(error => {
                        window.alert(`An error occurred:\n\n${error}`);
                    });
                }
            });
        }
    }

    function addNewDepictedForm(entityElement) {
        const session = new Session( 'www.wikidata.org', {
            formatversion: 2,
            origin: '*',
        }, {
            userAgent: 'Wikidata-Image-Positions (https://wd-image-positions.toolforge.org/)',
        } );
        const entity = entityElement.closest('.wd-image-positions--entity'),
              subjectId = entity.dataset.entityId,
              subjectDomain = entity.dataset.entityDomain,
              newDepictedFormRoot = document.createElement('div');
        newDepictedFormRoot.setAttribute("id", "new-depicted-form-root")
        entityElement.append(newDepictedFormRoot);

        createApp({
            template: `
<form class="wd-image-positions--add-new-depicted-form">
    <h3>Add more statements:</h3>
    <div class="wd-image-positions--add-new-depicted-form-row">
        <cdx-select
            v-model:selected="selectedProperty"
            :menu-items="properties"
        />
    </div>
    <div class="wd-image-positions--add-new-depicted-form-row">
        <p>Depicted item: </p>
        <cdx-lookup
            v-model:selected="selectedItem"
            :menu-items="searchResults"
            :menu-config="{'visible-item-limit': searchLimit}"
            :disabled="disabled"
            aria-label="Value"
            @input="onSearchInput"
            @load-more="onSearchLoadMore"
        />
        <p>Reference (optional):</p>
        <select name="referencetype" id="referencetype">
            <option value="none">Select Reference Type</option>
            <option value="P854">Reference URL</option>
            <option value="P248">Stated in (an object on Wikidata)</option>
        </select>
        <cdx-lookup
            v-model:selected="selectedReferenceItem"
            :menu-items="searchReferenceResults"
            :menu-config="{'visible-item-limit': searchLimit}"
            :disabled="disabled"
            aria-label="Reference"
            @input="onSearchReferenceInput"
            @load-more="onSearchReferenceLoadMore"
        />
    </div>
    <div class="wd-image-positions--add-new-depicted-form-row" id="reference-row">
    </div>
    <div class="wd-image-positions--add-new-depicted-form-row">
        <cdx-button
        :disabled="disabled"
        @click.prevent="onAddItem"
        >
        <cdx-icon :icon="cdxIconAdd" />
        Add statement
        </cdx-button>
    </div>
    <div class="wd-image-positions--add-new-depicted-form-row">
        <cdx-button
            :disabled="disabled"
            @click.prevent="onAddNonValue('somevalue')"
        >
            <cdx-icon :icon="cdxIconAdd" />
            Add “unknown value” statement
        </cdx-button>
        <!-- there’s no technical reason not to implement this, but it’s not really useful
        <cdx-button
            :disabled="disabled"
            @click.prevent="onAddNonValue('novalue')"
        >
            No value
        </cdx-button>
        -->
    </div>
</cdx-field>
`,
            components: codex,
            data() {
                const properties = Object.entries(depictedProperties).map(entry => ({
                    value: entry[0],
                    label: entry[1][0],
                }));
                return {
                    disabled: false,
                    properties,
                    selectedProperty: properties[0].value,
                    selectedItem: null,
                    selectedReferenceItem: null,
                    searchResults: [],
                    searchReferenceResults: [],
                    searchValue: '',
                    searchReferenceValue: '',
                    searchLimit: 5,
                    searchOffset: 0,
                    searchReferenceOffset: 0,
                    ...codexIcons,
                };
            },
            methods: {
                async onSearchInput(value) {
                    this.searchValue = value;
                    this.searchOffset = 0;
                    if (!value) {
                        this.searchResults = [];
                        return;
                    }
                    const searchResults = await this.doSearch(value, this.searchOffset);
                    if (this.searchValue !== value) {
                        return; // changed during the request
                    }
                    this.searchResults = searchResults;
                    this.searchOffset += this.searchLimit;
                },

                async onSearchReferenceInput(value) {
                    this.searchReferenceValue = value;
                    this.searchOffset = 0;
                    if (!value) {
                        this.searchReferenceResults = [];
                        return;
                    }
                    const dropdown = document.querySelector('#referencetype');
                    const toggle = document.querySelector('#qid-toggle');
                    if (dropdown.selectedIndex == 2 && toggle.checked == false) {
                        const newResults = await this.doSearch(value, this.searchResultsOffset);
                        if (this.searchReferenceValue !== value) {
                            return; // changed during the request
                        }
                        this.searchReferenceResults = newResults;
                        this.searchReferenceOffset += this.searchLimit;
                    } else {
                        this.searchReferenceResults = [];
                    }
                },

                async onSearchLoadMore() {
                    const value = this.searchValue;
                    const moreResults = await this.doSearch(value, this.searchOffset);
                    if (this.searchValue !== value) {
                        return; // changed during the request
                    }
                    this.searchResults.push(...moreResults);
                    this.searchOffset += this.searchLimit;
                },

                async onSearchReferenceLoadMore() {
                    const value = this.searchReferenceValue;
                    const moreResults = await this.doSearch(value, this.searchReferenceOffset);
                    if (this.searchReferenceValue !== value) {
                        return; // changed during the request
                    }
                    this.searchReferenceResults.push(...moreResults);
                    this.searchReferenceOffset += this.searchLimit;
                },

                async doSearch(value, offset) {
                    const response = await session.request({
                        action: 'wbsearchentities',
                        search: value,
                        language: 'en',
                        type: 'item',
                        limit: this.searchLimit,
                        continue: this.searchOffset,
                        props: set(),
                    });
                    return response.search.map(result => ({
                        value: result.id,
                        label: result.display?.label?.value,
                        description: result.display?.description?.value,
                        match: result.match.type === 'alias' ? `(${result.match.text})` : '',
                        language: {
                            label: result.display?.label?.language,
                            description: result.display?.description?.language,
                            match: result.match.type === 'alias' ? result.match.language : undefined,
                        },
                    }));
                },

                onAddItem() {
                    if (!this.selectedItem) {
                        return;
                    }
                    const formData = new FormData();
                    formData.append('snaktype', 'value');
                    formData.append('property_id', this.selectedProperty);
                    formData.append('item_id', this.selectedItem);

                    const dropdown = document.querySelector('#referencetype');
                    const toggle = document.querySelector('#qid-toggle');
                    if (dropdown.selectedIndex != 0 && (!this.searchReferenceValue || this.searchReferenceValue == '')) { 
                        // incomplete information
                        alert('Incomplete reference information. Either change reference type back to "select reference type" or complete information');
                        return;
                    } else if (dropdown.selectedIndex != 0) {
                        if (dropdown.selectedIndex == 2 && !this.selectedReferenceItem && toggle.checked == false) {
                            alert('No item has been selected. Please select an item that this reference was stated in and try again.');
                            return;
                        }

                        if (dropdown.selectedIndex == 2 && toggle.checked == true) {
                            if (!this.searchReferenceValue) {
                                alert('Incomplete reference information. Either change reference type back to "select reference type" or complete information');
                                return;
                            }
                            // make sure that a given QID is valid
                            if (this.searchReferenceValue[0] != "Q") {
                                alert("Given reference is not a valid QID. Please check and try again.");
                                return;
                            }
                            try {
                                let digits = BigInt(this.searchReferenceValue.substring(1));
                                console.log(digits);               
                            } catch (error) {
                                alert("Given reference is not a valid QID. Please check and try again.");
                                return;
                            }
                        }

                        formData.append('reference_type', dropdown.value)
                        if (dropdown.selectedIndex == 1) {
                            // 1 = reference URL
                            formData.append('reference_value', this.searchReferenceValue);
                        } else if (dropdown.selectedIndex == 2) {
                            // 2 = stated in                          
                            if (toggle.checked) {
                                formData.append('reference_value', this.searchReferenceValue);
                            } else {
                                formData.append('reference_value', this.selectedReferenceItem);
                            }

                            const pages = document.querySelector("#pages-input");
                            if (pages.value != "") {
                                formData.append('pages_value', pages.value);
                            }
                        }
                    }
                    this.addStatement(formData);
                },

                onAddNonValue(snakType) {
                    const formData = new FormData();
                    formData.append('snaktype', snakType);
                    this.addStatement(formData);
                },

                addStatement(formData) {
                    this.disabled = true;
                    formData.append('entity_id', subjectId);
                    formData.append('_csrf_token', csrfTokenElement.textContent);
                    fetch(`${baseUrl}/api/v1/add_statement_local/${subjectDomain}`, {
                        method: 'POST',
                        body: formData,
                        credentials: 'include',
                    }).then(response => {
                        if (response.ok) {
                            return response.json().then(json => {
                                const statementId = json.depicted.statement_id;
                                const propertyId = json.depicted.property_id;
                                let depictedsWithoutRegionList = entityElement.querySelector(
                                    `.wd-image-positions--depicteds-without-region__${propertyId} ul`,
                                );
                                if (!depictedsWithoutRegionList) {
                                    const depictedsWithoutRegionDiv = document.createElement('div'),
                                          depictedsWithoutRegionText = document.createTextNode(
                                              `${depictedProperties[propertyId]?.[1] || propertyId} with no region specified:`,
                                          );
                                    depictedsWithoutRegionList = document.createElement('ul');
                                    depictedsWithoutRegionDiv.classList.add('wd-image-positions--depicteds-without-region');
                                    depictedsWithoutRegionDiv.classList.add(`wd-image-positions--depicteds-without-region__${propertyId}`);
                                    depictedsWithoutRegionDiv.append(depictedsWithoutRegionText, depictedsWithoutRegionList);
                                    newDepictedFormRoot.insertAdjacentElement('beforebegin', depictedsWithoutRegionDiv);
                                }
                                const depicted = document.createElement('li');
                                depicted.classList.add('wd-image-positions--depicted-without-region');
                                depicted.dataset.statementId = statementId;
                                depicted.innerHTML = json.depicted_item_link;
                                depictedsWithoutRegionList.append(depicted);
                                addEditButton(depicted);
                                addRemoveButton(depicted);
                            });
                        } else {
                            return response.text().then(error => {
                                window.alert(`An error occurred:\n\n${error}`);
                            });
                        }
                    }).finally(() => {
                        this.disabled = false;
                    });
                }

            },
        }).mount(newDepictedFormRoot);
    }

    function addNewDepictedForms() {
        document.querySelectorAll('.wd-image-positions--entity').forEach(entityElement => {
            addNewDepictedForm(entityElement);
        });
    }

    function addDropDownEventListener() {
        function onDropDownChange() {
            const element = document.getElementById('referencetype');
            if (element) {
                if (element.value == "P248") {
                    // append the QID toggle
                    let toggleWrapper = document.createElement('label');
                    toggleWrapper.classList.add('switch');
                    toggleWrapper.setAttribute('id', 'toggle-wrapper');
                    let toggleExplainer = document.createElement('p');
                    toggleExplainer.innerHTML = "Toggle to cite known QID";
                    let toggleInput = document.createElement('input');
                    toggleInput.setAttribute('type', 'checkbox');
                    toggleInput.setAttribute('id', 'qid-toggle');
                    let toggleSpan = document.createElement('span');
                    toggleSpan.classList.add('slider');
                    toggleSpan.classList.add('round');

                    toggleWrapper.appendChild(toggleInput);
                    toggleWrapper.appendChild(toggleSpan);
                    
                    document.getElementById('reference-row').append(toggleExplainer);
                    document.getElementById('reference-row').append(toggleWrapper);

                    let pagesLabel = document.createElement('p');
                    pagesLabel.innerHTML = "Pages (optional)";
                    let pagesInput = document.createElement('input');
                    pagesInput.setAttribute('id', 'pages-input');
                    pagesInput.setAttribute('placeholder', '12-13');

                    document.getElementById('reference-row').append(pagesLabel);
                    document.getElementById('reference-row').append(pagesInput);

                } else {
                    document.getElementById('reference-row').innerHTML = '';
                }
            }
        }

        const element = document.getElementById('referencetype');
        element.addEventListener('change', onDropDownChange);

    }

    addEditButtons();
    addEditRegionButtons();
    initializeRegionCommentList();
    document.querySelectorAll('.wd-image-positions--depicted').forEach(div => {
        labelLocalQualifierStatement(div);
    });
    addNewDepictedForms();
    addCommentLabelsOwnUser();

    addDropDownEventListener();

    addUploadButton(document.querySelector('#new-depicted-form-root'));
}

setup();
