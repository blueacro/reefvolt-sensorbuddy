# Host unit tests for the ReefVolt CAN catalog.
# SPDX-License-Identifier: Apache-2.0

CC       ?= cc
CFLAGS    = -Wall -Wextra -Werror -std=c11 -g -O0
CPPFLAGS  = -I../include
BUILD_DIR = build

SRC  = ../src/reefvolt_can.c
TEST = test_reefvolt_can.c
BIN  = $(BUILD_DIR)/test_reefvolt_can

.PHONY: all test clean
all: test

$(BIN): $(SRC) $(TEST) ../include/reefvolt_can.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) $(SRC) $(TEST) -o $(BIN)

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

test: $(BIN)
	./$(BIN)

clean:
	rm -rf $(BUILD_DIR)
