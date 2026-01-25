/** @odoo-module **/

import { qweb as QWeb, _t } from 'web.core';
import SystrayMenu from 'web.SystrayMenu';
import Widget from 'web.Widget';
import rpc from 'web.rpc';

/**
 * AI Chat Systray Item - Icon trong thanh hệ thống
 */
var AIChatSystray = Widget.extend({
    name: 'ai_chat_systray',
    template: 'ai_integration.ChatSystray',
    sequence: 10,
    events: {
            'click .ai-systray-icon': '_onClickIcon',
            'click .ai-chat-toggle': '_onToggleChat',
            'click .ai-chat-close': '_onCloseChat',
            'click .ai-chat-send': '_onSendMessage',
            'keypress .ai-chat-input': '_onInputKeypress',
            'click .ai-quick-action': '_onQuickAction',
            'click .ai-confirm-btn': '_onConfirmAction',
            'click .ai-reject-btn': '_onRejectAction',
            'click .ai-clear-chat': '_onClearChat',
        },

        /**
         * @override
         */
        init: function () {
            this._super.apply(this, arguments);
            this.sessionId = null;
            this.messages = [];
            this.isOpen = false;
            this.isLoading = false;
            this.activeModel = null;
            this.activeResId = null;
            this.quickActions = [];
        },

        /**
         * @override
         */
        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                self._loadQuickActions();
            });
        },

        /**
         * Handle context update from other widgets
         */
        _onContextUpdate: function (data) {
            this.activeModel = data.model;
            this.activeResId = data.res_id;
            // Optionally reset session
            if (data.reset_session) {
                this.sessionId = null;
                this.messages = [];
            }
            this._loadQuickActions();
        },

        /**
         * Click on systray icon
         */
        _onClickIcon: function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            this._togglePanel();
        },

        /**
         * Toggle panel
         */
        _onToggleChat: function (ev) {
            ev.preventDefault();
            this._togglePanel();
        },

        /**
         * Toggle chat panel
         */
        _togglePanel: function () {
            this.isOpen = !this.isOpen;
            this.$('.ai-chat-dropdown').toggleClass('show', this.isOpen);
            
            if (this.isOpen && !this.sessionId) {
                this._initSession();
            }
        },

        /**
         * Close panel
         */
        _onCloseChat: function (ev) {
            ev.preventDefault();
            this.isOpen = false;
            this.$('.ai-chat-dropdown').removeClass('show');
        },

        /**
         * Initialize session
         */
        _initSession: function () {
            var self = this;
            rpc.query({
                route: '/ai/chat/session',
                params: {
                    active_model: this.activeModel,
                    active_res_id: this.activeResId,
                }
            }).then(function (result) {
                if (result.success) {
                    self.sessionId = result.session.id;
                    self._loadHistory();
                }
            });
        },

        /**
         * Load chat history
         */
        _loadHistory: function () {
            var self = this;
            if (!this.sessionId) return;

            rpc.query({
                route: '/ai/chat/history',
                params: {
                    session_id: this.sessionId,
                    limit: 30,
                }
            }).then(function (result) {
                if (result.success) {
                    self.messages = result.messages;
                    self._renderMessages();
                }
            });
        },

        /**
         * Load quick actions
         */
        _loadQuickActions: function () {
            var self = this;
            rpc.query({
                route: '/ai/chat/quick_actions',
                params: {
                    active_model: this.activeModel,
                }
            }).then(function (result) {
                if (result.success) {
                    self.quickActions = result.quick_actions;
                    self._renderQuickActions();
                }
            });
        },

        /**
         * Render quick actions
         */
        _renderQuickActions: function () {
            var $container = this.$('.ai-quick-actions');
            if (!$container.length) return;
            
            $container.empty();
            _.each(this.quickActions.slice(0, 4), function (action) {
                var $btn = $('<button>')
                    .addClass('btn btn-sm btn-outline-secondary ai-quick-action m-1')
                    .attr('data-prompt', action.prompt)
                    .text(action.label);
                $container.append($btn);
            });
        },

        /**
         * Render messages
         */
        _renderMessages: function () {
            var self = this;
            var $container = this.$('.ai-chat-messages');
            if (!$container.length) return;
            
            $container.empty();

            _.each(this.messages, function (msg) {
                var $msg = self._createMessageElement(msg);
                $container.append($msg);
            });

            $container.scrollTop($container[0].scrollHeight);
        },

        /**
         * Create message element
         */
        _createMessageElement: function (msg) {
            var roleClass = 'ai-msg-' + msg.role;
            var $msg = $('<div>').addClass('ai-message ' + roleClass);

            var $content = $('<div>').addClass('ai-msg-content');
            if (msg.content_html) {
                $content.html(msg.content_html);
            } else {
                $content.text(msg.content);
            }
            $msg.append($content);

            // Action buttons
            if (msg.requires_confirmation && !msg.action_confirmed) {
                var $actions = $('<div>').addClass('ai-msg-actions mt-2');
                $actions.append(
                    $('<button>')
                        .addClass('btn btn-sm btn-success ai-confirm-btn mr-1')
                        .attr('data-message-id', msg.id)
                        .html('<i class="fa fa-check"></i>')
                );
                $actions.append(
                    $('<button>')
                        .addClass('btn btn-sm btn-outline-danger ai-reject-btn')
                        .attr('data-message-id', msg.id)
                        .html('<i class="fa fa-times"></i>')
                );
                $content.append($actions);
            }

            return $msg;
        },

        /**
         * Handle keypress
         */
        _onInputKeypress: function (ev) {
            if (ev.which === 13 && !ev.shiftKey) {
                ev.preventDefault();
                this._onSendMessage(ev);
            }
        },

        /**
         * Send message
         */
        _onSendMessage: function (ev) {
            ev.preventDefault();
            var $input = this.$('.ai-chat-input');
            var message = $input.val().trim();

            if (!message || this.isLoading) return;

            $input.val('');

            this._addMessage({
                role: 'user',
                content: message,
            });

            this._setLoading(true);

            var self = this;
            rpc.query({
                route: '/ai/chat/send',
                params: {
                    session_id: this.sessionId,
                    message: message,
                    context: {
                        active_model: this.activeModel,
                        active_res_id: this.activeResId,
                    }
                }
            }).then(function (result) {
                self._setLoading(false);

                if (result && result.success) {
                    self.sessionId = result.session_id;
                    self._addMessage({
                        id: result.message_id,
                        role: 'assistant',
                        content: result.message,
                        requires_confirmation: result.requires_confirmation,
                    });
                } else {
                    var errorMsg = (result && result.error) ? result.error : 'Không thể xử lý yêu cầu';
                    self._addMessage({
                        role: 'assistant',
                        content: '❌ ' + errorMsg,
                    });
                }
            }).catch(function (error) {
                self._setLoading(false);
                var errorDetail = error.message || error.data?.message || 'Không thể kết nối server';
                console.error('AI Chat Error:', error);
                self._addMessage({
                    role: 'assistant',
                    content: '❌ Lỗi: ' + errorDetail,
                });
            });
        },

        /**
         * Add message to UI
         */
        _addMessage: function (msg) {
            this.messages.push(msg);
            var $container = this.$('.ai-chat-messages');
            if ($container.length) {
                var $msg = this._createMessageElement(msg);
                $container.append($msg);
                $container.scrollTop($container[0].scrollHeight);
            }
        },

        /**
         * Set loading state
         */
        _setLoading: function (loading) {
            this.isLoading = loading;
            this.$('.ai-chat-send').prop('disabled', loading);
            this.$('.ai-chat-loading').toggleClass('d-none', !loading);
        },

        /**
         * Quick action click
         */
        _onQuickAction: function (ev) {
            ev.preventDefault();
            var prompt = $(ev.currentTarget).data('prompt');
            if (prompt) {
                this.$('.ai-chat-input').val(prompt);
                this._onSendMessage(ev);
            }
        },

        /**
         * Confirm action
         */
        _onConfirmAction: function (ev) {
            ev.preventDefault();
            var messageId = $(ev.currentTarget).data('message-id');
            var self = this;

            $(ev.currentTarget).prop('disabled', true);

            rpc.query({
                route: '/ai/chat/confirm',
                params: {
                    session_id: this.sessionId,
                    message_id: messageId,
                }
            }).then(function (result) {
                if (result.success) {
                    $(ev.currentTarget).closest('.ai-msg-actions').html(
                        '<span class="text-success">✓</span>'
                    );
                    self._loadHistory();
                } else {
                    $(ev.currentTarget).prop('disabled', false);
                }
            });
        },

        /**
         * Reject action
         */
        _onRejectAction: function (ev) {
            ev.preventDefault();
            var messageId = $(ev.currentTarget).data('message-id');

            rpc.query({
                route: '/ai/chat/reject',
                params: {
                    session_id: this.sessionId,
                    message_id: messageId,
                }
            }).then(function (result) {
                if (result.success) {
                    $(ev.currentTarget).closest('.ai-msg-actions').html(
                        '<span class="text-muted">✗</span>'
                    );
                }
            });
        },

        /**
         * Clear chat
         */
        _onClearChat: function (ev) {
            ev.preventDefault();
            var self = this;

            if (!this.sessionId) return;

            rpc.query({
                route: '/ai/chat/clear',
                params: {
                    session_id: this.sessionId,
                }
            }).then(function (result) {
                if (result.success) {
                    self.messages = [];
                    self._renderMessages();
                }
            });
        },
    });

    // Add to systray
    SystrayMenu.Items.push(AIChatSystray);

    export default AIChatSystray;

