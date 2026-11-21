#ifndef __TRANSLATE_H__
#define __TRANSLATE_H__

int sanitize_path(const char *path);
int translate_open(const char *path, int flags);
int translate_set_readonly_dir(const char *path);
int translate_readonly_enabled(void);
int translate_readonly_allowed(const char *path);

#endif
